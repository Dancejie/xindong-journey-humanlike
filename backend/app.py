"""Heart Journey Cowork backend: SSO, PostgreSQL state, bounded Agents and media receipts."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import httpx
import psycopg
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row

from backend.agent_prompt import (
    build_agent_messages,
    build_chat_opening_messages,
    extract_json,
    fallback_chat_opening,
    validate_chat_opening,
)
from backend.day1_script import (
    build_day1_node_messages,
    install_cached_day1_script,
    install_day1_node_script,
    install_day1_script,
    validate_day1_node_script,
)
from backend.game_content import (
    CARD_PACKAGE,
    CHARACTER_CARD_MAP,
    CHARACTER_MAP,
    CHARACTERS,
    CONTENT_VERSION,
    active_cast_ids,
    available_chat_contexts,
    apply_choice,
    commit_agent_turn,
    create_snapshot,
    migrate_snapshot,
    normalize_conversation_context,
    project_view,
    validate_agent_turn,
)
from backend.story_director import (
    build_story_director_messages,
    commit_story_event,
    eligible_story_events,
    resolve_story_mission,
    validate_story_director_output,
)

ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"


def _load_props(path: str) -> dict[str, str]:
    props: dict[str, str] = {}
    try:
        with open(path) as source:
            for raw in source:
                line = raw.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    props[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return props


def _get_db_conn() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return psycopg.connect(database_url, row_factory=dict_row)
    props = _load_props("db.properties")
    if not props.get("db.host"):
        raise HTTPException(status_code=503, detail="数据库尚未配置")
    return psycopg.connect(
        host=props["db.host"], port=int(props["db.port"]), dbname=props["db.database"],
        user=props["db.username"], password=props["db.password"], row_factory=dict_row,
    )


def _parse_sso_user(decrypted_userinfo: Optional[str]) -> Optional[dict]:
    if not decrypted_userinfo:
        return None
    try:
        data = json.loads(decrypted_userinfo.encode("latin-1").decode("utf-8"))
    except Exception:
        return None
    user_id = data.get("userId") or data.get("id")
    if not user_id:
        return None
    return {
        "userId": str(user_id),
        "username": data.get("username") or data.get("name") or data.get("displayName") or "心动嘉宾",
        "email": data.get("email") or data.get("workEmail"),
    }


def _require_user(decrypted_userinfo: Optional[str], client_id: Optional[str] = None) -> dict:
    # Public deployments must never trust the internal SSO header supplied by
    # an arbitrary internet client. Bind identity exclusively to the anonymous
    # browser token in this mode; the SSO header is only authoritative behind
    # the internal gateway.
    if os.getenv("APP_AUTH_MODE", "sso").lower() == "public":
        normalized = (client_id or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9-]{16,64}", normalized):
            raise HTTPException(status_code=400, detail="访客身份无效，请刷新页面重试")
        return {"userId": f"public:{normalized}", "username": "心动嘉宾", "email": None}
    user = _parse_sso_user(decrypted_userinfo)
    if user:
        return user
    raise HTTPException(status_code=401, detail="请先通过小红书内网身份登录")


async def _llm_text(messages: list[dict], max_tokens: int = 500) -> str:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not deepseek_key:
        raise RuntimeError("DeepSeek is not configured")
    base_url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False, "thinking": {"type": "disabled"}},
        )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    text = str(choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    if not text:
        raise RuntimeError("DeepSeek returned no output text")
    return text


def _load_run(conn: psycopg.Connection, run_id: str, owner_id: str, for_update: bool = False) -> dict:
    suffix = " FOR UPDATE" if for_update else ""
    row = conn.execute(
        f"SELECT id, snapshot, revision FROM game_runs WHERE id = %s AND owner_id = %s{suffix}",
        (run_id, owner_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="没有找到这段心动旅程")
    snapshot = row["snapshot"]
    raw = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    migrated = migrate_snapshot(raw)
    assert migrated is not None
    return migrated


def _save_run(conn: psycopg.Connection, run_id: str, owner_id: str, snapshot: dict) -> None:
    conn.execute(
        "UPDATE game_runs SET snapshot = %s, revision = %s, updated_at = NOW() WHERE id = %s AND owner_id = %s",
        (json.dumps(snapshot, ensure_ascii=False), snapshot["revision"], run_id, owner_id),
    )


def _record_event(conn: psycopg.Connection, run_id: str, owner_id: str, event_type: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO game_events (run_id, owner_id, event_type, payload) VALUES (%s, %s, %s, %s)",
        (run_id, owner_id, event_type, json.dumps(payload, ensure_ascii=False)),
    )


async def _agent_turn(character: dict, snapshot: dict, message: str, conversation_context: dict | None = None) -> dict:
    card = CHARACTER_CARD_MAP[character["id"]]
    player_card = CHARACTER_CARD_MAP[snapshot["player"]["perspectiveCharacterId"]]
    messages = build_agent_messages(card, snapshot, message, player_card, conversation_context)
    payload: dict | None = None
    for attempt in range(2):
        try:
            payload = None
            raw = await _llm_text(messages, max_tokens=760)
            payload = extract_json(raw)
            validate_agent_turn(card, payload, snapshot, message)
            return payload
        except Exception as error:
            if attempt == 0:
                messages = [*messages, {"role": "user", "content": f"上一轮未通过人物与时间线合同：{error}。保持同一人物判断，重写完整 JSON；只使用当前已发生事实。若原因涉及重复，必须避开 usedTopics，并贡献一个新的具体事实、轻巧反应或可执行行动。"}]
                continue
            if isinstance(payload, dict) and any(term in str(error) for term in ("建议语", "followup", "mainline")):
                payload.pop("suggestions", None)
                validate_agent_turn(card, payload, snapshot, message)
                return payload
            raise
    raise RuntimeError("DeepSeek 角色判断没有通过合同")


async def _generate_day1_node_script(snapshot: dict, node_id: str) -> dict | None:
    """Generate only surface copy for the deterministic next node."""
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        return None
    messages = build_day1_node_messages(snapshot, node_id)
    for attempt in range(2):
        try:
            raw = await _llm_text(messages, max_tokens=1900)
            payload = extract_json(raw)
            normalized = validate_day1_node_script(snapshot, node_id, payload)
            return {"node": normalized}
        except Exception as error:
            if attempt == 0:
                protagonist_name = CHARACTER_MAP[snapshot["player"]["perspectiveCharacterId"]]["name"]
                messages = [*messages, {"role": "user", "content": (
                    f"上一稿未通过当前节点合同：{error}。保持人物卡和固定 choice id，只重写完整 node JSON。"
                    f"身份再次确认：玩家就是{protagonist_name}，‘你’就是{protagonist_name}，场内没有第二个{protagonist_name}，不得让{protagonist_name}作为NPC对你行动或说话。"
                )}]
    return None


async def _generate_day1_script(snapshot: dict) -> dict:
    """Install opening copy without putting a full LLM round on the start path.

    Existing reviewed DeepSeek cache remains the preferred flavor.  A newly
    added protagonist may not have a cached package yet; in that case the
    deterministic character-card fallback is good enough to open the door
    immediately.  Later committed nodes can still request their scoped
    DeepSeek rewrite through ``_generate_day1_node_script``.
    """
    cached = install_cached_day1_script(snapshot)
    if cached is not None:
        return cached
    return install_day1_script(snapshot, None)


async def _chat_opening(card: dict, snapshot: dict) -> dict:
    fallback = fallback_chat_opening(card, snapshot)
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        return fallback
    player_card = CHARACTER_CARD_MAP[snapshot["player"]["perspectiveCharacterId"]]
    messages = build_chat_opening_messages(card, snapshot, player_card)
    for attempt in range(2):
        try:
            raw = await _llm_text(messages, max_tokens=520)
            return validate_chat_opening(card, snapshot, extract_json(raw), player_card)
        except Exception as error:
            if attempt == 0:
                messages = [*messages, {"role": "user", "content": f"上一稿未通过首聊合同：{error}。请保持角色身份，并让建议语严格使用玩家人物卡，重写完整 JSON。"}]
    return fallback


async def _story_director_turn(snapshot: dict, candidates: list[dict]) -> dict:
    messages = build_story_director_messages(snapshot, candidates)
    raw = await _llm_text(messages, max_tokens=1100)
    payload = extract_json(raw)
    try:
        return validate_story_director_output(snapshot, candidates, payload)
    except ValueError as error:
        repair = [*messages, {"role": "user", "content": f"上一份 JSON 未通过事件合同：{error}。请重新输出完整 JSON；只写候选参与者的行动。"}]
        repaired_raw = await _llm_text(repair, max_tokens=1100)
        return validate_story_director_output(snapshot, candidates, extract_json(repaired_raw))


app = FastAPI(title="心动之旅：MBTI恋综模拟器")
_agent_windows: dict[str, list[float]] = {}
_agent_global_window: list[float] = []


def _enforce_agent_rate_limit(user_id: str) -> None:
    global _agent_global_window
    now = time.time()
    window_seconds = 600
    limit = max(1, int(os.getenv("AGENT_RATE_LIMIT", "20")))
    global_limit = max(limit, int(os.getenv("AGENT_GLOBAL_RATE_LIMIT", "200")))
    recent = [stamp for stamp in _agent_windows.get(user_id, []) if now - stamp < window_seconds]
    recent_global = [stamp for stamp in _agent_global_window if now - stamp < window_seconds]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="心动信号有点拥挤，请稍后再聊")
    if len(recent_global) >= global_limit:
        raise HTTPException(status_code=429, detail="今晚的心动信号已到上限，请稍后再试")
    recent.append(now)
    recent_global.append(now)
    _agent_windows[user_id] = recent
    _agent_global_window = recent_global


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "xindong-journey-humanlike",
        "contentVersion": CONTENT_VERSION,
        "characterCardContentVersion": CARD_PACKAGE["contentVersion"],
        "authMode": os.getenv("APP_AUTH_MODE", "sso"),
        "agentProvider": "deepseek" if os.getenv("DEEPSEEK_API_KEY") else "unconfigured",
        "databaseConfigured": bool(os.getenv("DATABASE_URL") or _load_props("db.properties").get("db.host")),
    }


@app.get("/api/whoami")
def whoami(decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    return JSONResponse(_require_user(decrypted_userinfo, x_client_id))


@app.get("/api/bootstrap")
def bootstrap(decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    user = _require_user(decrypted_userinfo, x_client_id)
    with _get_db_conn() as conn:
        row = conn.execute(
            "SELECT snapshot FROM game_runs WHERE owner_id = %s ORDER BY updated_at DESC LIMIT 1", (user["userId"],)
        ).fetchone()
    snapshot = row["snapshot"] if row else None
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    snapshot = migrate_snapshot(snapshot)
    return JSONResponse({
        "user": user, "characters": CHARACTERS, "view": project_view(snapshot) if snapshot else None,
        "rosterPolicy": {"librarySize": len(CHARACTERS), "runCastSize": 8, "selectionOrder": ["mbti", "gender", "character"]},
    })


@app.post("/api/runs", status_code=201)
async def start_run(body: dict, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    user = _require_user(decrypted_userinfo, x_client_id)
    mbti = str(body.get("mbti") or "INFP").upper()
    valid = {"INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"}
    if mbti not in valid:
        raise HTTPException(status_code=400, detail="请选择有效的 MBTI")
    perspective_character_id = str(body.get("perspectiveCharacterId") or "").strip()
    if perspective_character_id not in CHARACTER_MAP:
        raise HTTPException(status_code=400, detail="请选择一位有效的观察人物")
    if CHARACTER_MAP[perspective_character_id]["mbti"] != mbti:
        raise HTTPException(status_code=400, detail="所选 MBTI 与观察人物不一致，请先选 MBTI 再选对应角色")
    snapshot = create_snapshot(mbti, perspective_character_id)
    snapshot = await _generate_day1_script(snapshot)
    with _get_db_conn() as conn:
        conn.execute(
            "INSERT INTO app_users (id, username, email) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, email = EXCLUDED.email, updated_at = NOW()",
            (user["userId"], user["username"], user["email"]),
        )
        conn.execute(
            "INSERT INTO game_runs (id, owner_id, content_version, snapshot, revision) VALUES (%s, %s, %s, %s, %s)",
            (snapshot["runId"], user["userId"], snapshot["contentVersion"], json.dumps(snapshot, ensure_ascii=False), 0),
        )
        _record_event(conn, snapshot["runId"], user["userId"], "run.started", {"mbti": mbti, "perspectiveCharacterId": perspective_character_id, "scriptFlavorSource": snapshot["scriptFlavor"]["source"]})
        conn.commit()
    return JSONResponse(project_view(snapshot), status_code=201)


@app.post("/api/runs/{run_id}/choices")
async def choose(run_id: str, body: dict, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    user = _require_user(decrypted_userinfo, x_client_id)
    _enforce_agent_rate_limit(user["userId"])
    try:
        expected_revision = int(body.get("revision"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="缺少 revision")
    choice_id, character_id = str(body.get("choiceId") or ""), body.get("characterId")
    custom_text = body.get("customText")
    suggestion_id = body.get("suggestionId")
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"])
    if snapshot["revision"] != expected_revision:
        raise HTTPException(status_code=409, detail="状态已经更新，请刷新后重试")
    try:
        provisional, _ = apply_choice(snapshot, choice_id, character_id, custom_text, suggestion_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    contextual_payload = await _generate_day1_node_script(provisional, provisional["nodeId"])
    with _get_db_conn() as conn:
        current = _load_run(conn, run_id, user["userId"], for_update=True)
        if current["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="状态已经更新，请刷新后重试")
        try:
            next_snapshot, receipt = apply_choice(current, choice_id, character_id, custom_text, suggestion_id)
            if contextual_payload is not None:
                next_snapshot = install_day1_node_script(
                    next_snapshot, next_snapshot["nodeId"], contextual_payload,
                    {"provider": "deepseek", "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")},
                )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        _save_run(conn, run_id, user["userId"], next_snapshot)
        _record_event(conn, run_id, user["userId"], "story.choice", receipt)
        conn.commit()
    return JSONResponse({**project_view(next_snapshot), "receipt": receipt})


@app.post("/api/runs/{run_id}/agents/{character_id}/messages")
async def agent_message(run_id: str, character_id: str, body: dict, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    user = _require_user(decrypted_userinfo, x_client_id)
    character = CHARACTER_MAP.get(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="没有这位嘉宾")
    message = str(body.get("message") or "").strip()
    if not message or len(message) > 240:
        raise HTTPException(status_code=400, detail="请输入 1-240 个字")
    _enforce_agent_rate_limit(user["userId"])
    try:
        expected_revision = int(body.get("revision"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="缺少 revision")
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"])
    if snapshot["revision"] != expected_revision:
        raise HTTPException(status_code=409, detail="状态已经更新，请刷新后重试")
    if character_id == snapshot["player"]["perspectiveCharacterId"]:
        raise HTTPException(status_code=400, detail="当前观察视角就是这位嘉宾，不能和自己进入 1 对 1 私聊")
    if character_id not in active_cast_ids(snapshot):
        raise HTTPException(status_code=404, detail="这位嘉宾不在本季八人名单中")
    pending = snapshot.get("pendingInteraction") or {}
    if snapshot["nodeId"] == "guided-chat" and pending.get("status") == "required" and pending.get("targetCharacterId") != character_id:
        target_name = CHARACTER_MAP[pending["targetCharacterId"]]["name"]
        raise HTTPException(status_code=409, detail=f"节目组正在引导你先和{target_name}完成第一次破冰交流")
    supplied_context = body.get("context") if isinstance(body.get("context"), dict) else None
    try:
        presence = snapshot.get("characterPresence", {})
        context_input = dict(supplied_context or {})
        context_input["channel"] = "1v1"
        # Old clients did not send context. Keep them valid by resolving the
        # NPC's actual current venue server-side instead of silently assigning
        # the node's default venue.
        context_input.setdefault("locationId", presence.get(character_id))
        conversation_context = normalize_conversation_context(
            snapshot, context_input,
            participant_ids=[snapshot["player"]["perspectiveCharacterId"], character_id], channel="1v1",
        )
        if presence.get(character_id) != conversation_context["locationId"]:
            raise ValueError(f"{character['name']}现在不在{conversation_context['locationName']}")
        turn = await _agent_turn(character, snapshot, message, conversation_context)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        if isinstance(error, httpx.HTTPStatusError):
            safe_kind = f"http-{error.response.status_code}"
        elif isinstance(error, httpx.HTTPError):
            safe_kind = "http-network"
        else:
            safe_kind = "json" if isinstance(error, (json.JSONDecodeError, RuntimeError)) else "runtime"
        raise HTTPException(status_code=503, detail=f"DeepSeek 角色判断暂时没有完成（{safe_kind}），请重试这句话") from error
    with _get_db_conn() as conn:
        current = _load_run(conn, run_id, user["userId"], for_update=True)
        if current["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="关系状态已变化，这句话没有被重复写入")
        try:
            next_snapshot, receipt = commit_agent_turn(current, character_id, message, turn, conversation_context)
        except ValueError as error:
            raise HTTPException(status_code=502, detail=f"DeepSeek 角色输出未通过人物卡校验：{error}") from error
        reply = next_snapshot["echoMemories"][-1]["agentReply"]
        _save_run(conn, run_id, user["userId"], next_snapshot)
        conn.execute(
            "INSERT INTO agent_memories (run_id, owner_id, character_id, memory_id, player_text, agent_reply, intent_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (run_id, user["userId"], character_id, receipt["id"], message, reply, receipt["intentId"]),
        )
        _record_event(conn, run_id, user["userId"], "agent.memory", receipt)
        conn.commit()
    return JSONResponse({
        **project_view(next_snapshot), "reply": reply,
        "suggestions": receipt.get("suggestions", []),
        "suggestedPrompts": receipt.get("suggestedPrompts", []),
        "suggestionsSource": receipt.get("suggestionsSource"),
        "receipt": receipt,
    })


@app.get("/api/runs/{run_id}/agents/{character_id}/opener")
@app.get("/api/runs/{run_id}/agents/{character_id}/opening")
async def agent_opening(run_id: str, character_id: str, revision: Optional[int] = None, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    """Generate first-meeting or reopening copy without committing story state."""
    user = _require_user(decrypted_userinfo, x_client_id)
    _enforce_agent_rate_limit(user["userId"])
    card = CHARACTER_CARD_MAP.get(character_id)
    if not card:
        raise HTTPException(status_code=404, detail="没有这位嘉宾")
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"])
    if revision is not None and snapshot["revision"] != revision:
        raise HTTPException(status_code=409, detail="关系状态已经更新，请重新打开私聊")
    if character_id == snapshot["player"]["perspectiveCharacterId"]:
        raise HTTPException(status_code=400, detail="当前观察视角就是这位嘉宾，不能打开自己的私聊")
    if character_id not in active_cast_ids(snapshot):
        raise HTTPException(status_code=404, detail="这位嘉宾不在本季八人名单中")
    opening = await _chat_opening(card, snapshot)
    return JSONResponse({
        **opening,
        "opener": {"stageDirection": opening["stageDirection"], "line": opening["opening"], "dialogue": opening["opening"], "mode": opening["mode"]},
        "suggestedPrompts": opening["suggestions"],
        "suggestions": opening.get("typedSuggestions", []),
        "characterId": character_id, "revision": snapshot["revision"],
        "guided": (snapshot.get("pendingInteraction") or {}).get("targetCharacterId") == character_id,
    })


@app.get("/api/runs/{run_id}/chat-contexts")
def chat_contexts(run_id: str, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    """List only the guests currently present at each playable location."""
    user = _require_user(decrypted_userinfo, x_client_id)
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"])
    return JSONResponse({**available_chat_contexts(snapshot), "revision": snapshot["revision"]})


@app.post("/api/runs/{run_id}/group-messages")
@app.post("/api/runs/{run_id}/chats/group/messages")
async def group_message(run_id: str, body: dict, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    """Bounded location-aware group chat; each NPC keeps an independent memory."""
    user = _require_user(decrypted_userinfo, x_client_id)
    message = str(body.get("message") or "").strip()
    if not message or len(message) > 240:
        raise HTTPException(status_code=400, detail="请输入 1-240 个字")
    try:
        expected_revision = int(body.get("revision"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="缺少 revision")
    raw_participants = body.get("participantIds")
    if not isinstance(raw_participants, list):
        raise HTTPException(status_code=400, detail="群聊参与者必须是列表")
    if not all(isinstance(item, str) for item in raw_participants):
        raise HTTPException(status_code=400, detail="群聊参与者 ID 格式无效")
    participant_ids = list(dict.fromkeys(str(item) for item in raw_participants if isinstance(item, str)))
    _enforce_agent_rate_limit(user["userId"])
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"])
    if snapshot["revision"] != expected_revision:
        raise HTTPException(status_code=409, detail="群聊状态已经更新，请刷新后重试")
    pending = snapshot.get("pendingInteraction") or {}
    if snapshot["nodeId"] == "guided-chat" and pending.get("status") == "required":
        raise HTTPException(status_code=409, detail="先完成节目组安排的第一次 1 对 1 破冰，再发起群聊")
    perspective_id = snapshot["player"]["perspectiveCharacterId"]
    npc_ids = [character_id for character_id in participant_ids if character_id != perspective_id]
    if not 2 <= len(npc_ids) <= 4:
        raise HTTPException(status_code=400, detail="群聊请选择 2-4 位在场嘉宾")
    if any(character_id not in active_cast_ids(snapshot) for character_id in npc_ids):
        raise HTTPException(status_code=400, detail="群聊参与者不在本季八人名单中")
    supplied_context = body.get("context") if isinstance(body.get("context"), dict) else {}
    try:
        presence = snapshot.get("characterPresence", {})
        context_input = {**supplied_context, "channel": "group"}
        selected_locations = {presence.get(character_id) for character_id in npc_ids}
        if not context_input.get("locationId"):
            if len(selected_locations) != 1 or None in selected_locations:
                raise ValueError("群聊嘉宾不在同一地点，请先按地点筛选。")
            context_input["locationId"] = selected_locations.pop()
        context = normalize_conversation_context(
            snapshot, context_input,
            participant_ids=[perspective_id, *npc_ids], channel="group",
        )
        absent = [character_id for character_id in npc_ids if presence.get(character_id) != context["locationId"]]
        if absent:
            names = "、".join(CHARACTER_MAP[character_id]["name"] for character_id in absent if character_id in CHARACTER_MAP)
            raise ValueError(f"{names}现在不在{context['locationName']}")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    generated: list[tuple[str, dict]] = []
    for character_id in npc_ids:
        character = CHARACTER_MAP.get(character_id)
        if not character or character_id not in active_cast_ids(snapshot):
            raise HTTPException(status_code=400, detail="群聊参与者不在本季八人名单中")
        try:
            generated.append((character_id, await _agent_turn(character, snapshot, message, context)))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"{character['name']}的群聊回复暂时没有完成；本轮未写入任何记忆") from error
    with _get_db_conn() as conn:
        current = _load_run(conn, run_id, user["userId"], for_update=True)
        if current["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="群聊状态已经更新；本轮未重复写入")
        replies, receipts = [], []
        try:
            for character_id, turn in generated:
                current, receipt = commit_agent_turn(current, character_id, message, turn, context)
                memory = current["echoMemories"][-1]
                replies.append({
                    "characterId": character_id, "characterName": CHARACTER_MAP[character_id]["name"],
                    "reply": memory["agentReply"], "stageDirection": memory["stageDirection"],
                    "memoryId": memory["id"], "context": receipt["context"],
                })
                receipts.append(receipt)
                conn.execute(
                    "INSERT INTO agent_memories (run_id, owner_id, character_id, memory_id, player_text, agent_reply, intent_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (run_id, user["userId"], character_id, receipt["id"], message, memory["agentReply"], receipt["intentId"]),
                )
        except ValueError as error:
            raise HTTPException(status_code=502, detail=f"群聊角色输出未通过人物卡校验：{error}") from error
        _save_run(conn, run_id, user["userId"], current)
        _record_event(conn, run_id, user["userId"], "agent.group-memory", {"context": context, "receipts": receipts})
        conn.commit()
    return JSONResponse({**project_view(current), "replies": replies, "context": context, "receipts": receipts})


@app.post("/api/runs/{run_id}/story-director")
async def story_director(run_id: str, body: dict, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    """Ask DeepSeek to select one authored, currently eligible main-quest event."""
    user = _require_user(decrypted_userinfo, x_client_id)
    _enforce_agent_rate_limit(user["userId"])
    try:
        expected_revision = int(body.get("revision"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="缺少 revision")
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"])
    if snapshot["revision"] != expected_revision:
        raise HTTPException(status_code=409, detail="剧情状态已经更新，请刷新后重试")
    if snapshot["nodeId"] != "callback":
        raise HTTPException(status_code=409, detail="第一天先按节目流程完成初见、破冰、组队和心动短信；剧情导演会从第二天开始介入")
    candidates = eligible_story_events(snapshot)
    if not candidates:
        if snapshot.get("storyMission"):
            raise HTTPException(status_code=409, detail="请先完成或放弃当前主任务")
        raise HTTPException(status_code=409, detail="当前证据还不足以激活新主任务，先完成一次具体交流或剧情选择")
    try:
        proposal = await _story_director_turn(snapshot, candidates)
    except Exception as error:
        if isinstance(error, httpx.HTTPStatusError):
            safe_kind = f"http-{error.response.status_code}"
        elif isinstance(error, httpx.HTTPError):
            safe_kind = "http-network"
        else:
            safe_kind = "json" if isinstance(error, (json.JSONDecodeError, RuntimeError)) else "runtime"
        raise HTTPException(status_code=503, detail=f"DeepSeek 剧情导演暂时没有完成判断（{safe_kind}），请重试") from error
    with _get_db_conn() as conn:
        current = _load_run(conn, run_id, user["userId"], for_update=True)
        if current["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="剧情状态已变化，本次导演判断没有写入")
        current_candidates = eligible_story_events(current)
        try:
            next_snapshot, receipt = commit_story_event(current, current_candidates, proposal)
        except ValueError as error:
            raise HTTPException(status_code=502, detail=f"DeepSeek 剧情导演输出未通过事件合同：{error}") from error
        if receipt["kind"] == "story-director-wait":
            return JSONResponse({**project_view(current), "directorHint": receipt, "receipt": receipt})
        _save_run(conn, run_id, user["userId"], next_snapshot)
        _record_event(conn, run_id, user["userId"], "story.event.activated", receipt)
        conn.commit()
    return JSONResponse({**project_view(next_snapshot), "receipt": receipt})


@app.post("/api/runs/{run_id}/story-missions/{mission_id}/resolve")
def story_mission_resolve(run_id: str, mission_id: str, body: dict, decrypted_userinfo: Optional[str] = Header(None, alias="Decrypted-Userinfo"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> JSONResponse:
    """Commit a player-visible mission outcome; no LLM is allowed to patch state here."""
    user = _require_user(decrypted_userinfo, x_client_id)
    try:
        expected_revision = int(body.get("revision"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="缺少 revision")
    outcome = str(body.get("outcome") or "")
    evidence = str(body.get("evidence") or "")
    with _get_db_conn() as conn:
        snapshot = _load_run(conn, run_id, user["userId"], for_update=True)
        if snapshot["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="剧情状态已经更新，请刷新后重试")
        try:
            next_snapshot, receipt = resolve_story_mission(snapshot, mission_id, outcome, evidence)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        _save_run(conn, run_id, user["userId"], next_snapshot)
        _record_event(conn, run_id, user["userId"], "story.mission.resolved", receipt)
        conn.commit()
    return JSONResponse({**project_view(next_snapshot), "receipt": receipt})


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
if (FRONTEND_DIST / "media").exists():
    app.mount("/media", StaticFiles(directory=str(FRONTEND_DIST / "media")), name="media")


@app.get("/")
def index():
    if not INDEX_HTML.exists():
        return HTMLResponse("<h1>《心动之旅》前端尚未构建</h1>", status_code=503)
    return FileResponse(INDEX_HTML)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    real = FRONTEND_DIST / full_path
    if real.is_file():
        return FileResponse(real)
    return FileResponse(INDEX_HTML) if INDEX_HTML.exists() else JSONResponse({"error": "frontend missing"}, status_code=503)
