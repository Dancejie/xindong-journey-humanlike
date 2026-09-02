from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse

import backend.app as app_module
import backend.init_db as init_db_module
from backend.app import (
    _db_schema,
    _enforce_agent_rate_limit,
    _request_provider,
    _require_user,
    agent_opening,
    bootstrap,
    choose,
    health,
    spa_fallback,
)
from backend.agent_prompt import fallback_chat_opening
from backend.game_content import CHARACTER_CARD_MAP, active_cast_ids, create_snapshot, project_view


class PublicAuthTests(unittest.TestCase):
    def test_public_mode_ignores_spoofed_internal_sso_header(self) -> None:
        spoofed = json.dumps({"userId": "victim", "username": "Victim"})
        with patch.dict(os.environ, {"APP_AUTH_MODE": "public"}, clear=False):
            user = _require_user(spoofed, "browser-client-123456")
        self.assertEqual(user["userId"], "public:browser-client-123456")
        self.assertEqual(user["username"], "心动嘉宾")

    def test_public_mode_requires_valid_anonymous_client_id(self) -> None:
        with patch.dict(os.environ, {"APP_AUTH_MODE": "public"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                _require_user(None, "short")
        self.assertEqual(raised.exception.status_code, 400)

    def test_sso_mode_still_accepts_internal_identity(self) -> None:
        payload = json.dumps({"userId": "internal-user", "username": "测试用户"})
        with patch.dict(os.environ, {"APP_AUTH_MODE": "sso"}, clear=False):
            user = _require_user(payload, None)
        self.assertEqual(user["userId"], "internal-user")
        self.assertEqual(user["username"], "测试用户")


class PublicRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._agent_windows.clear()
        app_module._agent_global_window.clear()

    def tearDown(self) -> None:
        app_module._agent_windows.clear()
        app_module._agent_global_window.clear()

    def test_global_limit_covers_multiple_anonymous_visitors(self) -> None:
        env = {"AGENT_RATE_LIMIT": "2", "AGENT_GLOBAL_RATE_LIMIT": "3"}
        with patch.dict(os.environ, env, clear=False), patch("backend.app.time.time", return_value=100.0):
            _enforce_agent_rate_limit("public:a")
            _enforce_agent_rate_limit("public:a")
            _enforce_agent_rate_limit("public:b")
            with self.assertRaises(HTTPException) as raised:
                _enforce_agent_rate_limit("public:b")
        self.assertEqual(raised.exception.status_code, 429)


class DatabaseSchemaTests(unittest.TestCase):
    def test_humanlike_schema_is_shared_by_runtime_and_initializer(self) -> None:
        with patch.dict(os.environ, {"DB_SCHEMA": "xindong_journey_humanlike"}, clear=False):
            self.assertEqual(_db_schema(), "xindong_journey_humanlike")
            self.assertEqual(init_db_module.schema_name(), "xindong_journey_humanlike")

    def test_unsafe_schema_identifier_is_rejected(self) -> None:
        with patch.dict(os.environ, {"DB_SCHEMA": "public; DROP SCHEMA public"}, clear=False):
            with self.assertRaises(RuntimeError):
                _db_schema()
            with self.assertRaises(RuntimeError):
                init_db_module.schema_name()


class ProviderRoutingTests(unittest.TestCase):
    def test_request_provider_is_allowlisted_configured_and_never_cross_falls_back(self) -> None:
        env = {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "deepseek-configured",
            "DOTS_API_KEY": "dots-configured",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual("deepseek", _request_provider(None, required=True))
            self.assertEqual("dots", _request_provider("DOTS", required=True))
            with self.assertRaises(HTTPException) as illegal:
                _request_provider("openai", required=True)
        self.assertEqual(400, illegal.exception.status_code)

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "configured"}, clear=True):
            with self.assertRaises(HTTPException) as unconfigured:
                _request_provider("dots", required=True)
        self.assertEqual(400, unconfigured.exception.status_code)

    def test_all_generation_routes_accept_x_llm_provider(self) -> None:
        expected_paths = {
            "/api/runs",
            "/api/runs/{run_id}/choices",
            "/api/runs/{run_id}/agents/{character_id}/messages",
            "/api/runs/{run_id}/agents/{character_id}/opener",
            "/api/runs/{run_id}/agents/{character_id}/opening",
            "/api/runs/{run_id}/group-messages",
            "/api/runs/{run_id}/chats/group/messages",
            "/api/runs/{run_id}/story-director",
        }
        routes = {route.path: route for route in app_module.app.routes if route.path in expected_paths}
        self.assertEqual(expected_paths, set(routes))
        for path, route in routes.items():
            aliases = {parameter.alias for parameter in route.dependant.header_params}
            self.assertIn("X-LLM-Provider", aliases, path)

    def test_health_and_bootstrap_expose_names_only(self) -> None:
        class Result:
            @staticmethod
            def fetchone():
                return None

        class Connection:
            def execute(self, *args, **kwargs):
                return Result()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        env = {
            "APP_AUTH_MODE": "public",
            "LLM_PROVIDER": "dots",
            "DOTS_API_KEY": "dots-secret",
            "DOTS_API_BASE": "https://private-dots.example/v1",
            "DOTS_MODEL": "private-dots-model",
            "DEEPSEEK_API_KEY": "deepseek-secret",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch("backend.app._get_db_conn", return_value=Connection()),
        ):
            health_payload = health()
            bootstrap_payload = json.loads(bootstrap(None, "browser-client-123456").body)
        expected = {"default": "dots", "current": "dots", "available": ["deepseek", "dots"]}
        self.assertEqual(expected, health_payload["llmProviders"])
        self.assertEqual(expected, bootstrap_payload["llmProviders"])
        serialized = json.dumps({"health": health_payload, "bootstrap": bootstrap_payload})
        for secret in ("dots-secret", "private-dots.example", "private-dots-model", "deepseek-secret"):
            self.assertNotIn(secret, serialized)


class GenerationSourceTests(unittest.IsolatedAsyncioTestCase):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def commit(self):
            return None

    async def test_choice_response_reports_contextual_or_engine_fallback(self) -> None:
        async def request(generation):
            snapshot = create_snapshot("ENFP", "jiangmi")
            choice_id = project_view(snapshot)["node"]["choices"][0]["id"]
            with (
                patch.dict(os.environ, {"DOTS_API_KEY": "configured-for-test"}, clear=False),
                patch("backend.app._require_user", return_value={"userId": "test-user"}),
                patch("backend.app._enforce_agent_rate_limit"),
                patch("backend.app._get_db_conn", return_value=self.Connection()),
                patch("backend.app._load_run", side_effect=[deepcopy(snapshot), deepcopy(snapshot)]),
                patch("backend.app._generate_day1_node_script", AsyncMock(return_value=generation)),
                patch("backend.app.install_day1_node_script", side_effect=lambda state, *_: state),
                patch("backend.app._save_run"),
                patch("backend.app._record_event"),
            ):
                response = await choose(
                    snapshot["runId"],
                    {"revision": snapshot["revision"], "choiceId": choice_id},
                    x_llm_provider="dots",
                )
            return json.loads(response.body)

        contextual = await request(({"node": {}}, {"provider": "dots", "model": "test-model"}))
        self.assertEqual("dots-contextual", contextual["generationSource"])
        self.assertEqual("dots", contextual["llmProvider"])

        fallback = await request(None)
        self.assertEqual("engine-fallback", fallback["generationSource"])
        self.assertIsNone(fallback["llmProvider"])

    async def test_opener_response_reports_provider_or_engine_fallback(self) -> None:
        snapshot = create_snapshot("ENFP", "jiangmi")
        target_id = next(character_id for character_id in active_cast_ids(snapshot) if character_id != "jiangmi")
        opening = fallback_chat_opening(CHARACTER_CARD_MAP[target_id], snapshot)

        async def request(generator):
            with (
                patch.dict(os.environ, {"DOTS_API_KEY": "configured-for-test"}, clear=False),
                patch("backend.app._require_user", return_value={"userId": "test-user"}),
                patch("backend.app._enforce_agent_rate_limit"),
                patch("backend.app._get_db_conn", return_value=self.Connection()),
                patch("backend.app._load_run", return_value=deepcopy(snapshot)),
                patch("backend.app._chat_opening", AsyncMock(return_value=(opening, generator))),
            ):
                response = await agent_opening(
                    snapshot["runId"], target_id, revision=snapshot["revision"], x_llm_provider="dots",
                )
            return json.loads(response.body)

        generated = await request({"provider": "dots", "model": "test-model"})
        self.assertEqual("dots-opener", generated["generationSource"])
        self.assertEqual("dots", generated["llmProvider"])

        fallback = await request(None)
        self.assertEqual("engine-fallback", fallback["generationSource"])
        self.assertIsNone(fallback["llmProvider"])


class StaticFileBoundaryTests(unittest.TestCase):
    def test_spa_fallback_only_serves_files_inside_frontend_dist(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            root = Path(raw_dir)
            frontend = root / "dist"
            frontend.mkdir()
            index = frontend / "index.html"
            index.write_text("safe index", encoding="utf-8")
            asset = frontend / "safe.txt"
            asset.write_text("safe asset", encoding="utf-8")
            outside = root / "private.txt"
            outside.write_text("private", encoding="utf-8")
            (frontend / "outside-link.txt").symlink_to(outside)
            with (
                patch.object(app_module, "FRONTEND_DIST", frontend),
                patch.object(app_module, "INDEX_HTML", index),
            ):
                safe_response = spa_fallback("safe.txt")
                self.assertIsInstance(safe_response, FileResponse)
                self.assertEqual(asset.resolve(), Path(safe_response.path).resolve())
                for hostile_path in ("../private.txt", "../../private.txt", "outside-link.txt"):
                    with self.subTest(path=hostile_path):
                        blocked = spa_fallback(hostile_path)
                        self.assertIsInstance(blocked, JSONResponse)
                        self.assertEqual(404, blocked.status_code)


if __name__ == "__main__":
    unittest.main()
