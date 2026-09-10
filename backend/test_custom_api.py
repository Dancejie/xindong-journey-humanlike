from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import unittest
from copy import deepcopy
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from PIL import Image
from fastapi.testclient import TestClient
import psycopg
from psycopg import sql

from backend.custom_characters import validate_profile, normalize_photo, build_player_card, apply_card_copy
from backend.game_content import CHARACTER_CARDS


def fixture_body():
    output = io.BytesIO()
    picture = Image.new('RGB', (300, 400), '#c79a88')
    exif = Image.Exif()
    exif[270] = 'PRIVATE metadata'
    picture.save(output, 'JPEG', exif=exif)
    return {'name': '可晴', 'mbti': 'ISTP', 'gender': 'female', 'age': 26,
            'occupation': '产品设计师', 'about': '喜欢周末去海边散步。', 'preferences': '喜欢直白聊天，不喝咖啡',
            'boundaries': '不愿被催促做决定', 'photoDataUrl': 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode(),
            'consent': True, 'requestId': str(uuid4())}


class CustomInputTests(unittest.TestCase):
    def test_normalized_photo_has_no_metadata(self):
        data, digest = normalize_photo(fixture_body()['photoDataUrl'])
        with Image.open(io.BytesIO(data)) as photo:
            self.assertEqual('JPEG', photo.format)
            self.assertFalse(photo.getexif())
        self.assertEqual(64, len(digest))
        self.assertNotIn(b'PRIVATE', data)

    def test_photo_and_adult_consent_are_validated(self):
        for override in ({'age': 17}, {'age': True}, {'consent': False}, {'gender': 'x'}, {'mbti': 'ABCD'}, {'name': 'a' * 25}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                validate_profile({**fixture_body(), **override})
        for photo in ('data:image/svg+xml;base64,YQ==', 'https://internal/secret.jpg', 'data:image/jpeg;base64,aGVsbG8='):
            with self.subTest(photo=photo), self.assertRaises(ValueError):
                normalize_photo(photo)

    def test_no_template_biography_or_image_leaks_to_custom_player(self):
        body = fixture_body()
        template = next(card for card in CHARACTER_CARDS if card['mbti'] == body['mbti'])
        card = build_player_card(validate_profile(body), 'custom-' + str(uuid4()), '/api/custom-media/' + 'a' * 64, template)
        serialized = json.dumps(card, ensure_ascii=False)
        self.assertNotIn(template['names']['primary'], serialized)
        self.assertNotIn(template['portrait'], serialized)
        self.assertEqual('', card['video'])
        self.assertEqual('未提供，不推断', card['psychology']['fears'][0])
        revised = apply_card_copy(card, {'introduction': '大家好，我是可晴，ISTP，平时做产品设计师。来这里，想和大家慢慢认识。', 'register': '简短自然，先说具体想法'})
        self.assertNotEqual(card['customIntroduction'], revised['customIntroduction'])
        self.assertEqual(body['occupation'], revised['sourceProfile']['facts']['occupation'])


@unittest.skipUnless(os.getenv('CUSTOM_TEST_DATABASE_URL'), 'requires an explicitly selected disposable test database schema')
class CustomApiDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.init_db import SCHEMA
        cls.database = os.environ['CUSTOM_TEST_DATABASE_URL']
        cls.schema = 'custom_player_test_' + uuid4().hex[:16]
        cls.env = patch.dict(os.environ, {'APP_AUTH_MODE': 'public', 'DATABASE_URL': cls.database, 'DB_SCHEMA': cls.schema,
                                        'LLM_PROVIDER': 'deepseek', 'DEEPSEEK_API_KEY': '', 'DOTS_API_KEY': '',
                                        'CUSTOM_VIDEO_API_KEY': '', 'FUMIN_API_KEY': ''})
        cls.env.start()
        with psycopg.connect(cls.database) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
            conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(cls.schema)))
            conn.execute(SCHEMA)
        import backend.app as app_module
        cls.app_module = app_module
        cls.no_paid_llm = patch('backend.app.call_text', new=AsyncMock(side_effect=RuntimeError('offline test')))
        cls.no_paid_llm.start()
        cls.client = TestClient(app_module.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.no_paid_llm.stop()
        cls.env.stop()
        assert cls.schema.startswith('custom_player_test_') and len(cls.schema) == 35
        with psycopg.connect(cls.database) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        self.headers = {'X-Client-Id': 'test-client-' + uuid4().hex}

    def create(self):
        body = fixture_body()
        response = self.client.post('/api/custom-characters', json=body, headers=self.headers)
        self.assertEqual(201, response.status_code, response.text)
        return response.json(), body

    def budget_with_room_for_one(self):
        # Tests share a disposable schema; preserve the durable ledger semantics.
        with self.app_module._get_db_conn() as conn:
            spent = conn.execute('SELECT COALESCE(SUM(reserved_cny),0) AS n FROM custom_video_budget_jobs').fetchone()['n']
        return str(spent + 3)

    def test_create_auto_video_submits_once_and_refresh_never_pays(self):
        body = {**fixture_body(), 'autoVideo': True, 'maxCostCny': 3}
        config = {'available': True, 'estimatedCostCny': 3, 'durationSeconds': 10, 'resolution': '480p', 'modelLabel': 'Seedance 2.0'}
        director = {'specHash': 'auto-spec-hash', 'requestedModel': 'seedance-2.0', 'photoSha256': 'hash', 'durationSeconds': 10}
        with patch('backend.custom_video.config_status', return_value=config), \
             patch('backend.custom_video.build_director_card', return_value=deepcopy(director)), \
             patch('backend.custom_video.submit_video', new=AsyncMock(return_value='auto-job-123')) as submit, \
             patch('backend.custom_video.poll_video', new=AsyncMock(return_value={'status': 'processing'})), \
             patch.dict(os.environ, {'CUSTOM_VIDEO_BUDGET_CNY': self.budget_with_room_for_one()}):
            created = self.client.post('/api/custom-characters', json=body, headers=self.headers)
            self.assertEqual(201, created.status_code, created.text)
            profile = created.json()
            self.assertEqual('reserved', profile['video']['status'])
            self.assertEqual(1, submit.await_count)
            submitted_director = submit.call_args.args[1]
            self.assertEqual(10, submitted_director['durationSeconds'])
            self.assertEqual('create-role-auto-v1', submitted_director['approval']['authorizationMode'])
            self.assertEqual(3, submitted_director['approval']['maxCostCny'])
            self.assertFalse(submitted_director['doNotSubmit'])
            repeated = self.client.post('/api/custom-characters', json=body, headers=self.headers)
            self.assertEqual(profile['id'], repeated.json()['id'])
            listing = self.client.get('/api/custom-characters', headers=self.headers).json()
            self.assertFalse(listing['generation']['available'])
            self.assertIn('额度已用完', listing['generation']['reason'])
            self.assertEqual(listing['generation'], listing['characters'][0]['generation'])
            self.assertEqual(1, len(listing['characters']))
            path = '/api/custom-characters/' + profile['id']
            self.assertEqual('processing', self.client.get(path, headers=self.headers).json()['video']['status'])
            self.client.get(path, headers=self.headers)
            self.client.post(path + '/video', json={'confirmed': True, 'maxCostCny': 3}, headers=self.headers)
            self.assertEqual(1, submit.await_count)

    def test_photo_only_and_legacy_create_do_not_auto_submit(self):
        with patch('backend.custom_video.submit_video', new=AsyncMock()) as submit:
            for extra in ({'autoVideo': False, 'maxCostCny': 3}, {}):
                body = {**fixture_body(), **extra}
                created = self.client.post('/api/custom-characters', json=body, headers=self.headers)
                self.assertEqual(201, created.status_code, created.text)
                self.assertEqual('planned', created.json()['video']['status'])
            self.client.get('/api/custom-characters', headers=self.headers)
            submit.assert_not_awaited()
            invalid = self.client.post('/api/custom-characters', json={**fixture_body(), 'autoVideo': 'true'}, headers=self.headers)
            self.assertEqual(400, invalid.status_code)

    def test_create_row_locks_run_off_the_async_event_loop(self):
        from backend.custom_api import load_custom
        checked = []

        def off_loop_load(conn, identifier, owner, *, locked=False):
            if locked:
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    checked.append(identifier)
                else:
                    self.fail('A synchronous row-lock wait can deadlock the provider poll on this event loop')
            return load_custom(conn, identifier, owner, locked=locked)

        with patch('backend.custom_api.load_custom', side_effect=off_loop_load), \
             patch('backend.custom_video.config_status', return_value={'available': False, 'reason': '未配置视频'}):
            created = self.client.post('/api/custom-characters', json={**fixture_body(), 'autoVideo': True}, headers=self.headers)
            self.assertEqual(201, created.status_code, created.text)
            self.assertEqual([created.json()['id']] * 2, checked)
            self.assertIn('未配置视频', created.json()['video']['message'])

    def test_auto_preflight_failure_retains_photo_and_never_requeues(self):
        ready = {'available': True, 'estimatedCostCny': 3, 'durationSeconds': 10}
        cases = [({'available': False, 'reason': '视频通道尚未配置'}, '9', 3, '视频通道尚未配置'),
                 (ready, '0', 3, '额度已用完'),
                 (ready, '999', 1, '费用发生变化'),
                 (ready, '999', None, '确认本次生成费用')]
        with patch('backend.custom_video.submit_video', new=AsyncMock()) as submit:
            for config, budget, quote, message in cases:
                with self.subTest(message=message), patch('backend.custom_video.config_status', return_value=config), \
                     patch.dict(os.environ, {'CUSTOM_VIDEO_BUDGET_CNY': budget}):
                    body = {**fixture_body(), 'autoVideo': True, 'maxCostCny': quote}
                    result = self.client.post('/api/custom-characters', json=body, headers=self.headers)
                    self.assertEqual(201, result.status_code, result.text)
                    profile = result.json()
                    self.assertEqual('planned', profile['video']['status'])
                    self.assertIn(message, profile['video']['message'])
                    self.assertEqual(200, self.client.get(profile['character']['portrait']).status_code)
                # Fixing config later must not replay old creation consent on reload.
                with patch('backend.custom_video.config_status', return_value=ready), \
                     patch.dict(os.environ, {'CUSTOM_VIDEO_BUDGET_CNY': '999'}):
                    self.client.get('/api/custom-characters/' + profile['id'], headers=self.headers)
                    repeated = self.client.post('/api/custom-characters', json=body, headers=self.headers)
                    self.assertEqual(profile['id'], repeated.json()['id'])
                    self.assertEqual('planned', repeated.json()['video']['status'])
            submit.assert_not_awaited()

    def test_exhausted_project_budget_is_shared_across_owners_and_gets_never_pay(self):
        exhausted_message = '本项目动态视频额度已用完，暂不提交新任务；已有角色和视频仍可使用'
        first, _ = self.create()
        second_headers = {'X-Client-Id': 'second-owner-' + uuid4().hex}
        second_response = self.client.post('/api/custom-characters', json=fixture_body(), headers=second_headers)
        self.assertEqual(201, second_response.status_code, second_response.text)
        second = second_response.json()
        config = {'available': True, 'estimatedCostCny': 2, 'durationSeconds': 10,
                  'resolution': '480p', 'modelLabel': 'Seedance 2.0 Mini'}
        director = {'specHash': 'shared-cap-spec', 'requestedModel': 'seedance-2.0-mini',
                    'photoSha256': 'hash', 'durationSeconds': 10}
        expected = {**config, 'available': False, 'reason': exhausted_message}
        # Only three additional yuan remain: a two-yuan reservation leaves a
        # positive balance that is nevertheless insufficient for another task.
        with patch('backend.custom_video.config_status', return_value=config), \
             patch('backend.custom_video.build_director_card', return_value=deepcopy(director)), \
             patch('backend.custom_video.submit_video', new=AsyncMock(return_value='shared-cap-job')) as submit, \
             patch('backend.custom_video.poll_video', new=AsyncMock(return_value={'status': 'processing'})), \
             patch.dict(os.environ, {'CUSTOM_VIDEO_BUDGET_CNY': self.budget_with_room_for_one()}):
            for headers in (self.headers, second_headers):
                self.assertEqual(config, self.client.get('/api/custom-characters', headers=headers).json()['generation'])
            first_path = '/api/custom-characters/' + first['id']
            accepted = self.client.post(first_path + '/video', json={'confirmed': True, 'maxCostCny': 2}, headers=self.headers)
            self.assertEqual(202, accepted.status_code, accepted.text)
            self.assertEqual(expected, accepted.json()['generation'])
            with self.app_module._get_db_conn() as conn:
                ledger_before = conn.execute('SELECT COUNT(*) AS jobs, SUM(reserved_cny) AS reserved FROM custom_video_budget_jobs').fetchone()
            for _ in range(3):
                for headers, profile in ((self.headers, first), (second_headers, second)):
                    listing = self.client.get('/api/custom-characters', headers=headers).json()
                    self.assertEqual(expected, listing['generation'])
                    self.assertEqual(1, len(listing['characters']))
                    self.assertEqual(expected, listing['characters'][0]['generation'])
                    detail = self.client.get('/api/custom-characters/' + profile['id'], headers=headers).json()
                    self.assertEqual(expected, detail['generation'])
                    self.assertEqual(200, self.client.get(detail['character']['portrait']).status_code)
            blocked = self.client.post('/api/custom-characters/' + second['id'] + '/video',
                                       json={'confirmed': True, 'maxCostCny': 2}, headers=second_headers)
            self.assertEqual(409, blocked.status_code, blocked.text)
            self.assertEqual(exhausted_message, blocked.json()['detail'])
            with self.app_module._get_db_conn() as conn:
                ledger_after = conn.execute('SELECT COUNT(*) AS jobs, SUM(reserved_cny) AS reserved FROM custom_video_budget_jobs').fetchone()
            self.assertEqual(ledger_before, ledger_after)
            self.assertEqual(1, submit.await_count)

    def test_auto_submission_uncertain_is_not_retried(self):
        from backend.custom_video import VideoSubmissionUncertainError
        config = {'available': True, 'estimatedCostCny': 3, 'durationSeconds': 10}
        director = {'specHash': 'uncertain-spec', 'requestedModel': 'seedance-2.0', 'photoSha256': 'hash', 'durationSeconds': 10}
        with patch('backend.custom_video.config_status', return_value=config), \
             patch('backend.custom_video.build_director_card', return_value=director), \
             patch('backend.custom_video.submit_video', new=AsyncMock(side_effect=VideoSubmissionUncertainError('network uncertain'))) as submit, \
             patch.dict(os.environ, {'CUSTOM_VIDEO_BUDGET_CNY': self.budget_with_room_for_one()}):
            body = {**fixture_body(), 'autoVideo': True, 'maxCostCny': 3}
            created = self.client.post('/api/custom-characters', json=body, headers=self.headers).json()
            path = '/api/custom-characters/' + created['id']
            self.assertEqual('needs_review', self.client.get(path, headers=self.headers).json()['video']['status'])
            self.client.post('/api/custom-characters', json=body, headers=self.headers)
            repeated = self.client.post(path + '/video', json={'confirmed': True, 'maxCostCny': 3}, headers=self.headers)
            self.assertEqual('needs_review', repeated.json()['video']['status'])
            self.assertEqual(1, submit.await_count)

    def test_create_idempotency_ownership_run_resume_media_and_erasure(self):
        profile, body = self.create()
        identifier = profile['id']
        repeated = self.client.post('/api/custom-characters', json=body, headers=self.headers)
        self.assertEqual(identifier, repeated.json()['id'])
        self.assertEqual(1, len(self.client.get('/api/custom-characters', headers=self.headers).json()['characters']))
        stranger = {'X-Client-Id': 'different-client-' + uuid4().hex}
        self.assertEqual(404, self.client.get('/api/custom-characters/' + identifier, headers=stranger).status_code)
        self.assertEqual(404, self.client.post('/api/runs', json={'mbti': 'ISTP', 'customCharacterId': identifier}, headers=stranger).status_code)
        photo_url = profile['character']['portrait']
        photo = self.client.get(photo_url)
        self.assertEqual('image/jpeg', photo.headers['content-type'])
        self.assertEqual('private, no-store', photo.headers['cache-control'])
        partial = self.client.get(photo_url, headers={'Range': 'bytes=0-31'})
        self.assertEqual(206, partial.status_code)
        self.assertEqual(32, len(partial.content))
        self.assertEqual(416, self.client.get(photo_url, headers={'Range': 'bytes=999999-'}).status_code)
        self.assertEqual(404, self.client.get('/api/custom-media/guess').status_code)
        run = self.client.post('/api/runs', json={'mbti': 'ISTP', 'customCharacterId': identifier, 'customPlayerCard': {'id': 'forged'}}, headers=self.headers)
        self.assertEqual(201, run.status_code, run.text)
        view = run.json()
        self.assertNotIn('customPlayerCard', view['snapshot'])
        self.assertEqual(identifier, view['snapshot']['player']['perspectiveCharacterId'])
        self.assertEqual(identifier, view['snapshot']['player']['customCharacterId'])
        self.assertEqual(8, len(view['characters']))
        self.assertEqual('可晴', next(c['name'] for c in view['characters'] if c['id'] == identifier))
        resumed = self.client.get('/api/bootstrap', headers=self.headers).json()['view']
        self.assertEqual(identifier, resumed['snapshot']['player']['customCharacterId'])
        self.assertNotIn('userProfile', json.dumps(resumed))
        self.assertNotIn('photoDataUrl', json.dumps(profile))
        self.assertNotIn('video_job', json.dumps(profile))
        self.assertEqual(200, self.client.delete('/api/custom-characters/' + identifier, headers=self.headers).status_code)
        self.assertEqual(404, self.client.get(photo_url).status_code)
        self.assertIsNone(self.client.get('/api/bootstrap', headers=self.headers).json()['view'])

    def test_video_cap_is_reserved_once_candidate_requires_approval(self):
        profile, _ = self.create()
        identifier = profile['id']
        path = '/api/custom-characters/' + identifier
        config = {'available': True, 'estimatedCostCny': 3, 'durationSeconds': 10}
        director = {'specHash': 'spec-hash', 'requestedModel': 'seedance-2.0', 'photoSha256': 'hash', 'durationSeconds': 10}
        with patch('backend.custom_video.config_status', return_value=config), \
             patch('backend.custom_video.build_director_card', return_value=deepcopy(director)), \
             patch('backend.custom_video.submit_video', new=AsyncMock(return_value='job-123')) as submit, \
             patch('backend.custom_video.poll_video', new=AsyncMock(return_value={'status': 'succeeded', 'video_url': 'https://allowed.example/video.mp4'})), \
             patch('backend.custom_video.download_candidate', new=AsyncMock(return_value=b'validated-mp4-fixture')) as download, \
             patch.dict(os.environ, {'CUSTOM_VIDEO_BUDGET_CNY': self.budget_with_room_for_one()}):
            self.assertEqual(400, self.client.post(path + '/video', json={}, headers=self.headers).status_code)
            self.assertEqual(409, self.client.post(path + '/video', json={'confirmed': True, 'maxCostCny': 1}, headers=self.headers).status_code)
            accepted = self.client.post(path + '/video', json={'confirmed': True, 'maxCostCny': 3}, headers=self.headers)
            self.assertEqual(202, accepted.status_code, accepted.text)
            self.client.post(path + '/video', json={'confirmed': True, 'maxCostCny': 3}, headers=self.headers)
            self.assertEqual(1, submit.await_count)
            submitted_director = submit.call_args.args[1]
            self.assertFalse(submitted_director['doNotSubmit'])
            self.assertEqual(3, submitted_director['approval']['maxCostCny'])
            candidate = self.client.get(path, headers=self.headers).json()
            download.assert_awaited_once_with('https://allowed.example/video.mp4', expected_duration_seconds=10)
            self.assertEqual('candidate', candidate['video']['status'])
            self.assertFalse(candidate['generation']['available'])
            self.assertEqual('', candidate['character']['video'])
            approved = self.client.post(path + '/video/approve', json={}, headers=self.headers).json()
            self.assertFalse(approved['generation']['available'])
            self.assertEqual(approved['video']['videoUrl'], approved['character']['video'])
            self.assertEqual(200, self.client.get(approved['character']['video']).status_code)
            self.client.delete(path, headers=self.headers)
            next_profile, _ = self.create()
            blocked = self.client.post('/api/custom-characters/' + next_profile['id'] + '/video', json={'confirmed': True, 'maxCostCny': 3}, headers=self.headers)
            self.assertEqual(409, blocked.status_code, blocked.text)
            self.assertEqual(1, submit.await_count)


if __name__ == '__main__':
    unittest.main()
