"""Owner-scoped custom characters and durable, one-shot media jobs."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import time
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import Response

from backend.agent_prompt import extract_json
from backend.custom_characters import (
    MAX_REQUEST_BYTES, apply_card_copy, build_player_card, card_generation_messages,
    normalize_photo, validate_profile,
)
from backend import custom_video
from backend.game_content import CHARACTER_CARDS, _public_character


class _PrivateMediaLogFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(re.sub(r'(/api/custom-media/)[0-9a-f]{64}', r'\1[private]', value)
                                if isinstance(value, str) else value for value in record.args)
        return True


def _object(value):
    return json.loads(value) if isinstance(value, str) else value


def load_custom(conn, character_id: str, owner_id: str, *, locked: bool = False) -> dict:
    if not re.fullmatch(r'custom-[0-9a-f-]{36}', character_id):
        raise HTTPException(404, '没有找到你的自定义人物')
    row = conn.execute(
        'SELECT id, owner_id, profile, card, video_status, video_error, video_token, video_job, photo_sha256 '
        'FROM custom_characters WHERE id = %s AND owner_id = %s' + (' FOR UPDATE' if locked else ''),
        (character_id, owner_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, '没有找到你的自定义人物')
    return {**row, **{key: _object(row[key]) for key in ('profile', 'card', 'video_job')}}


def hydrate_custom_snapshot(conn, snapshot: dict | None, owner_id: str) -> dict | None:
    """Use the current approved media without trusting any client-supplied card."""
    if not snapshot:
        return snapshot
    snapshot = _object(snapshot)
    custom_id = (snapshot.get('player') or {}).get('customCharacterId') or (snapshot.get('customPlayerCard') or {}).get('id')
    if custom_id:
        row = load_custom(conn, str(custom_id), owner_id)
        snapshot = {**snapshot, 'customPlayerCard': row['card']}
    return snapshot


VIDEO_MESSAGES = {
    'planned': '可以先用照片开局，动态形象按需生成。',
    'reserved': '正在准备动态形象，请稍候。',
    'submitted': '动态形象已提交生成。',
    'processing': '正在生成动态形象，你可以先用照片进入剧情。',
    'candidate': '动态形象已生成，请预览确认是你，再用于剧情。',
    'approved': '已使用你确认的动态形象。',
    'failed': '本次生成未完成，不会自动重试扣费；仍可用照片开局。',
    'needs_review': '生成状态需要核实，已停止再次提交，避免重复扣费；仍可用照片开局。',
}


VIDEO_BUDGET_EXHAUSTED = '本项目动态视频额度已用完，暂不提交新任务；已有角色和视频仍可使用'


def video_generation_status(conn) -> dict:
    config = custom_video.config_status()
    if not config['available']:
        return config
    cost = Decimal(str(config['estimatedCostCny']))
    budget = Decimal(os.getenv('CUSTOM_VIDEO_BUDGET_CNY', '0'))
    # This read-only summary covers the whole project, including reservations
    # whose characters were deleted. Submission still checks under its lock.
    spent = conn.execute('SELECT COALESCE(SUM(reserved_cny),0) AS n FROM custom_video_budget_jobs').fetchone()['n']
    if not cost.is_finite() or cost <= 0 or not budget.is_finite() or spent + cost > budget:
        return {**config, 'available': False, 'reason': VIDEO_BUDGET_EXHAUSTED}
    return config


def public_profile(row: dict, conn, *, generation: dict | None = None) -> dict:
    card = row['card']
    character = _public_character(card)
    character.update(isCustom=True, portraitKind='uploaded-identity', mediaFallbackKind='uploaded-photo')
    # Even the owner preview has no reason to receive invented private fields.
    for key in ('privateFear', 'memorySeed'):
        character.pop(key, None)
    status = row['video_status']
    job = row.get('video_job') or {}
    director = job.get('director') or {}
    return {
        'id': row['id'], 'character': character,
        'cardPreview': {'introduction': card['customIntroduction'], 'voice': card['voice']['register'],
                        'boundary': card['userProfile']['boundaries'], 'preferences': row['profile']['preferences'],
                        'source': card.get('customCopySource', 'user-profile')},
        'video': {'status': status, 'message': (row.get('video_error') if status == 'planned' else None) or VIDEO_MESSAGES.get(status, VIDEO_MESSAGES['needs_review']),
                  'durationSeconds': director.get('durationSeconds'), 'resolution': director.get('resolution'),
                  'requestedModel': director.get('requestedModel'), 'usedModel': job.get('usedModel'),
                  'videoUrl': f"/api/custom-media/{row['video_token']}" if status in ('candidate', 'approved') and row['video_token'] else None},
        'generation': generation if generation is not None else video_generation_status(conn),
    }


def make_custom_router(get_db, require_user, request_provider, llm_text) -> APIRouter:
    access_logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, _PrivateMediaLogFilter) for item in access_logger.filters):
        access_logger.addFilter(_PrivateMediaLogFilter())
    router = APIRouter()

    @router.post('/api/custom-characters', status_code=201)
    async def create_custom(request: Request, background_tasks: BackgroundTasks, decrypted_userinfo: Optional[str] = Header(None, alias='Decrypted-Userinfo'),
                            x_client_id: Optional[str] = Header(None, alias='X-Client-Id'),
                            x_llm_provider: Optional[str] = Header(None, alias='X-LLM-Provider')):
        user = require_user(decrypted_userinfo, x_client_id)
        # Bound the stream before JSON/base64 decoding, including chunked uploads.
        buffer = bytearray()
        async for chunk in request.stream():
            if len(buffer) + len(chunk) > MAX_REQUEST_BYTES:
                raise HTTPException(413, '照片过大，请使用不超过 8 MB 的照片')
            buffer.extend(chunk)
        try:
            body = json.loads(buffer)
            if not isinstance(body, dict):
                raise ValueError('请填写人物资料')
            profile = validate_profile(body)
            # Only the new form explicitly covers automatic transmission/one paid
            # task. Older clients' photo-only consent cannot be upgraded silently.
            if 'autoVideo' in body and not isinstance(body['autoVideo'], bool):
                raise ValueError('动态形象选项无效')
            profile['autoVideoRequested'] = body.get('autoVideo') is True
            photo, photo_hash = normalize_photo(body.get('photoDataUrl'))
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error)) from error
        request_key = str(body.get('requestId') or uuid4())
        if not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', request_key):
            raise HTTPException(400, '创建请求标识无效')
        provider = request_provider(x_llm_provider, required=False)
        character_id, photo_token = f'custom-{uuid4()}', secrets.token_hex(32)
        template = next(card for card in CHARACTER_CARDS if card['mbti'] == profile['mbti'])
        card = build_player_card(profile, character_id, f'/api/custom-media/{photo_token}', template)
        with get_db() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('custom-character-cap'))")
            existing = conn.execute('SELECT id FROM custom_characters WHERE owner_id = %s AND request_key = %s', (user['userId'], request_key)).fetchone()
            if existing:
                return public_profile(load_custom(conn, existing['id'], user['userId']), conn)
            count = conn.execute('SELECT COUNT(*) AS n FROM custom_characters WHERE owner_id = %s', (user['userId'],)).fetchone()['n']
            total = conn.execute('SELECT COUNT(*) AS n FROM custom_characters').fetchone()['n']
            if count >= 5 or total >= max(1, int(os.getenv('CUSTOM_CHARACTER_GLOBAL_LIMIT', '1000'))):
                raise HTTPException(429, '自定义人物储存已达上限，请先删除不再使用的人物')
            conn.execute('INSERT INTO app_users (id, username, email) VALUES (%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                         (user['userId'], user['username'], user['email']))
            conn.execute('INSERT INTO custom_characters (id, owner_id, request_key, profile, card, photo, photo_token, photo_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                         (character_id, user['userId'], request_key, json.dumps(profile, ensure_ascii=False), json.dumps(card, ensure_ascii=False), photo, photo_token, photo_hash))
            conn.commit()
        try:
            result = await asyncio.wait_for(llm_text(card_generation_messages(profile, card), max_tokens=550, provider=provider), timeout=18)
            text = result.text if hasattr(result, 'text') else str(result)
            card = apply_card_copy(card, extract_json(text))
            card['customCopySource'] = 'llm'
        except Exception:
            # No second provider, no paid retry, no lost upload on a provider timeout.
            card['customCopySource'] = 'user-profile'
        def save_card_copy():
            with get_db() as conn:
                current = load_custom(conn, character_id, user['userId'], locked=True)
                # A user may recover the saved card in another tab while copy generation
                # is still running. Never overwrite media they have since approved.
                card['video'] = current['card']['video']
                card['media'] = current['card']['media']
                conn.execute('UPDATE custom_characters SET card=%s, updated_at=NOW() WHERE id=%s AND owner_id=%s',
                             (json.dumps(card, ensure_ascii=False), character_id, user['userId']))
                conn.commit()
        # A poll may hold this row while awaiting the provider. Never wait for
        # its lock synchronously on the event loop needed to finish that poll.
        await asyncio.to_thread(save_card_copy)
        if profile['autoVideoRequested']:
            try:
                # Budget/row locks must run off the async event loop: another tab
                # may be polling a job while holding that row lock across await.
                result, director = await asyncio.to_thread(
                    reserve_video, character_id, user['userId'], body.get('maxCostCny'), 'create-role-auto-v1',
                )
                if director is not None:
                    background_tasks.add_task(perform_submission, character_id, user['userId'], director)
                return result
            except HTTPException as error:
                # Failed configuration/price/budget preflight never loses the card
                # and never queues a job for a later page refresh.
                message = f'本次未提交视频：{error.detail}。人物卡已保存，可以先用照片游玩。'
                def save_preflight_message():
                    with get_db() as conn:
                        conn.execute("UPDATE custom_characters SET video_error=%s WHERE id=%s AND owner_id=%s AND video_status='planned'", (message, character_id, user['userId']))
                        conn.commit()
                await asyncio.to_thread(save_preflight_message)
        with get_db() as conn:
            return public_profile(load_custom(conn, character_id, user['userId']), conn)

    @router.get('/api/custom-characters')
    def list_custom(decrypted_userinfo: Optional[str] = Header(None, alias='Decrypted-Userinfo'), x_client_id: Optional[str] = Header(None, alias='X-Client-Id')):
        user = require_user(decrypted_userinfo, x_client_id)
        with get_db() as conn:
            rows = conn.execute('SELECT id FROM custom_characters WHERE owner_id=%s ORDER BY created_at DESC', (user['userId'],)).fetchall()
            generation = video_generation_status(conn)
            return {'characters': [public_profile(load_custom(conn, row['id'], user['userId']), conn, generation=generation) for row in rows],
                    'generation': generation}

    async def perform_submission(character_id: str, owner: str, director: dict):
        job_id = None
        try:
            with get_db() as conn:
                photo_row = conn.execute('SELECT photo FROM custom_characters WHERE id=%s AND owner_id=%s', (character_id, owner)).fetchone()
            if not photo_row:
                return
            job_id = await custom_video.submit_video(bytes(photo_row['photo']), director)
            with get_db() as conn:
                conn.execute("UPDATE custom_characters SET video_status='submitted', video_job=%s, updated_at=NOW() WHERE id=%s AND owner_id=%s",
                             (json.dumps({'jobId': job_id, 'director': director, 'submittedAt': time.time()}), character_id, owner))
                conn.execute("UPDATE custom_video_budget_jobs SET status='submitted' WHERE character_id=%s", (character_id,))
                conn.commit()
        except Exception as error:
            # Every uncertain exception keeps its reservation. Neither browser reload nor
            # process restart can cause automatic re-submission.
            recovered_job = job_id or getattr(error, 'job_id', None)
            state = 'needs_review' if recovered_job or isinstance(error, custom_video.VideoSubmissionUncertainError) else 'failed'
            with get_db() as conn:
                conn.execute('UPDATE custom_characters SET video_status=%s, updated_at=NOW() WHERE id=%s AND owner_id=%s', (state, character_id, owner))
                if recovered_job:
                    conn.execute("UPDATE custom_characters SET video_job=video_job || %s::jsonb WHERE id=%s AND owner_id=%s",
                                 (json.dumps({'jobId': recovered_job}), character_id, owner))
                conn.execute('UPDATE custom_video_budget_jobs SET status=%s WHERE character_id=%s', (state, character_id))
                conn.commit()

    def reserve_video(character_id: str, owner: str, max_cost, authorization_mode: str):
        """Shared atomic reservation for create-time and explicit legacy-card requests."""
        with get_db() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('custom-video-budget'))")
            row = load_custom(conn, character_id, owner, locked=True)
            if row['video_status'] != 'planned':
                return public_profile(row, conn), None
            config = custom_video.config_status()
            if not config['available']:
                raise HTTPException(503, config.get('reason') or '动态视频通道尚未配置')
            cost = Decimal(str(config['estimatedCostCny']))
            budget = Decimal(os.getenv('CUSTOM_VIDEO_BUDGET_CNY', '0'))
            try:
                confirmed_cost = Decimal(str(max_cost))
            except Exception:
                raise HTTPException(400, '请确认本次生成费用')
            if not confirmed_cost.is_finite() or confirmed_cost < cost:
                raise HTTPException(409, '生成费用发生变化，请刷新并重新确认')
            spent = conn.execute('SELECT COALESCE(SUM(reserved_cny),0) AS n FROM custom_video_budget_jobs').fetchone()['n']
            if cost <= 0 or not cost.is_finite() or not budget.is_finite() or spent + cost > budget:
                raise HTTPException(409, VIDEO_BUDGET_EXHAUSTED)
            director = custom_video.build_director_card(row['card'], row['photo_sha256'])
            reservation_id = str(uuid4())
            director['doNotSubmit'] = False
            director['approval'] = {'confirmed': True, 'specHash': director['specHash'], 'referenceHash': row['photo_sha256'],
                                    'budgetRef': reservation_id, 'reviewer': owner, 'authorizationMode': authorization_mode,
                                    'reviewedAt': datetime.now(timezone.utc).isoformat(), 'maxCostCny': float(cost)}
            conn.execute('INSERT INTO custom_video_budget_jobs (id, character_id, reserved_cny) VALUES (%s,%s,%s)', (reservation_id, character_id, cost))
            conn.execute("UPDATE custom_characters SET video_status='reserved', video_error=NULL, video_job=%s, updated_at=NOW() WHERE id=%s",
                         (json.dumps({'director': director, 'reservedAt': time.time()}), character_id))
            conn.commit()
            result = public_profile(load_custom(conn, character_id, owner), conn)
        return result, director

    @router.post('/api/custom-characters/{character_id}/video', status_code=202)
    def generate_video(character_id: str, body: dict, background_tasks: BackgroundTasks,
                             decrypted_userinfo: Optional[str] = Header(None, alias='Decrypted-Userinfo'), x_client_id: Optional[str] = Header(None, alias='X-Client-Id')):
        user = require_user(decrypted_userinfo, x_client_id)
        if body.get('confirmed') is not True:
            raise HTTPException(400, '请先确认单次生成费用和照片传输授权')
        result, director = reserve_video(character_id, user['userId'], body.get('maxCostCny'), 'manual-existing-role-v1')
        if director is not None:
            background_tasks.add_task(perform_submission, character_id, user['userId'], director)
        return result

    @router.get('/api/custom-characters/{character_id}')
    async def get_custom(character_id: str, decrypted_userinfo: Optional[str] = Header(None, alias='Decrypted-Userinfo'), x_client_id: Optional[str] = Header(None, alias='X-Client-Id')):
        user = require_user(decrypted_userinfo, x_client_id)
        with get_db() as conn:
            row = load_custom(conn, character_id, user['userId'])
            if row['video_status'] == 'reserved' and time.time() - row['video_job'].get('reservedAt', 0) > 180:
                conn.execute("UPDATE custom_characters SET video_status='needs_review' WHERE id=%s AND video_status='reserved'", (character_id,))
                conn.commit()
                row = load_custom(conn, character_id, user['userId'])
            if row['video_status'] not in ('submitted', 'processing'):
                return public_profile(row, conn)
            # Only one status/download operation per job even across workers/tabs.
            locked = conn.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS ok', ('custom-video:' + character_id,)).fetchone()['ok']
            if not locked:
                return public_profile(row, conn)
            row = load_custom(conn, character_id, user['userId'], locked=True)
            if row['video_status'] not in ('submitted', 'processing'):
                return public_profile(row, conn)
            if time.time() - row['video_job'].get('lastCheckedAt', 0) < 4:
                return public_profile(row, conn)
            try:
                result = await custom_video.poll_video(row['video_job']['jobId'], expected_model=row['video_job']['director']['requestedModel'])
                status = result['status']
                if status == 'succeeded':
                    media = await custom_video.download_candidate(
                        result['video_url'], expected_duration_seconds=row['video_job']['director'].get('durationSeconds', 5),
                    )
                    token = secrets.token_hex(32)
                    conn.execute("UPDATE custom_characters SET video_status='candidate', video=%s, video_token=%s, updated_at=NOW() WHERE id=%s", (media, token, character_id))
                    conn.execute("UPDATE custom_video_budget_jobs SET status='candidate' WHERE character_id=%s", (character_id,))
                elif status in ('failed', 'cancelled', 'expired'):
                    conn.execute("UPDATE custom_characters SET video_status='failed', updated_at=NOW() WHERE id=%s", (character_id,))
                    conn.execute("UPDATE custom_video_budget_jobs SET status='failed' WHERE character_id=%s", (character_id,))
                else:
                    conn.execute("UPDATE custom_characters SET video_status='processing', updated_at=NOW() WHERE id=%s", (character_id,))
                conn.execute("UPDATE custom_characters SET video_job=video_job || %s::jsonb WHERE id=%s", (json.dumps({'lastCheckedAt': time.time(), 'usedModel': result.get('usedModel')}), character_id))
                conn.commit()
            except custom_video.VideoCandidateValidationError:
                conn.execute("UPDATE custom_characters SET video_status='needs_review', updated_at=NOW() WHERE id=%s", (character_id,))
                conn.execute("UPDATE custom_video_budget_jobs SET status='needs_review' WHERE character_id=%s", (character_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                # A polling/network failure does not justify another paid job.
                return public_profile(row, conn)
            return public_profile(load_custom(conn, character_id, user['userId']), conn)

    @router.post('/api/custom-characters/{character_id}/video/approve')
    def approve_video(character_id: str, decrypted_userinfo: Optional[str] = Header(None, alias='Decrypted-Userinfo'), x_client_id: Optional[str] = Header(None, alias='X-Client-Id')):
        user = require_user(decrypted_userinfo, x_client_id)
        with get_db() as conn:
            row = load_custom(conn, character_id, user['userId'], locked=True)
            if row['video_status'] not in ('candidate', 'approved'):
                raise HTTPException(409, '动态形象尚未完成，请稍后预览')
            card = row['card']
            card['video'] = f"/api/custom-media/{row['video_token']}"
            card['media'].update(status='approved-runtime', fallbackKind='uploaded-photo')
            conn.execute("UPDATE custom_characters SET video_status='approved', card=%s, updated_at=NOW() WHERE id=%s", (json.dumps(card, ensure_ascii=False), character_id))
            conn.execute("UPDATE custom_video_budget_jobs SET status='approved' WHERE character_id=%s", (character_id,))
            conn.commit()
            return public_profile(load_custom(conn, character_id, user['userId']), conn)

    @router.delete('/api/custom-characters/{character_id}')
    def delete_custom(character_id: str, decrypted_userinfo: Optional[str] = Header(None, alias='Decrypted-Userinfo'), x_client_id: Optional[str] = Header(None, alias='X-Client-Id')):
        user = require_user(decrypted_userinfo, x_client_id)
        with get_db() as conn:
            load_custom(conn, character_id, user['userId'], locked=True)
            conn.execute("DELETE FROM game_runs WHERE owner_id=%s AND snapshot->'player'->>'perspectiveCharacterId'=%s", (user['userId'], character_id))
            conn.execute('DELETE FROM custom_characters WHERE owner_id=%s AND id=%s', (user['userId'], character_id))
            conn.commit()
        return {'deleted': True}

    @router.get('/api/custom-media/{token}')
    def private_media(token: str, request: Request):
        # Capability URLs are unguessable, revocable and absent from public catalogs.
        # They allow <img>/<video> without exposing the account bearer token.
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise HTTPException(404, '图片或视频不可用')
        with get_db() as conn:
            row = conn.execute('SELECT photo AS data, FALSE AS is_video FROM custom_characters WHERE photo_token=%s UNION ALL SELECT video AS data, TRUE AS is_video FROM custom_characters WHERE video_token=%s AND video_status IN (\'candidate\',\'approved\')', (token, token)).fetchone()
        if not row or row['data'] is None:
            raise HTTPException(404, '图片或视频已删除')
        data = bytes(row['data'])
        mime = 'video/mp4' if row['is_video'] else 'image/jpeg'
        headers = {'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff', 'Accept-Ranges': 'bytes'}
        requested_range = request.headers.get('range')
        if requested_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested_range)
            if not match or not (match[1] or match[2]):
                return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{len(data)}'})
            start = int(match[1]) if match[1] else max(0, len(data) - int(match[2]))
            end = min(int(match[2]), len(data) - 1) if match[1] and match[2] else len(data) - 1
            if start > end or start >= len(data):
                return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{len(data)}'})
            return Response(data[start:end + 1], status_code=206, media_type=mime, headers={**headers, 'Content-Range': f'bytes {start}-{end}/{len(data)}'})
        return Response(data, media_type=mime, headers=headers)

    return router
