from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import backend.app as app_module
import backend.init_db as init_db_module
from backend.app import _db_schema, _enforce_agent_rate_limit, _require_user


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


if __name__ == "__main__":
    unittest.main()
