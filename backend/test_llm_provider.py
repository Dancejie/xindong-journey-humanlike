from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import httpx

from backend.llm_provider import (
    ProviderNotConfiguredError,
    ProviderResponseError,
    UnsupportedProviderError,
    call_text,
    provider_status,
)


class LLMProviderTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_dots_uses_api_key_header_openai_payload_and_visible_content(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json={
                "model": "dots3-note-prev",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "更像真人的一句回应。",
                        "reasoning_content": "private reasoning must not be returned",
                    },
                }],
            })

        env = {
            "LLM_PROVIDER": "dots",
            "DOTS_API_KEY": "dots-secret-for-test",
            "DOTS_API_BASE": "https://note3-prev-api.askdiandian.com/v1",
            "DOTS_MODEL": "dots3-note-prev",
            "DOTS_ENABLE_THINKING": "false",
        }
        transport = httpx.MockTransport(handler)
        with patch.dict(os.environ, env, clear=True):
            async with httpx.AsyncClient(transport=transport) as client:
                result = await call_text(
                    [{"role": "user", "content": "你好"}],
                    max_tokens=321,
                    provider="dots",
                    client=client,
                )

        self.assertEqual("https://note3-prev-api.askdiandian.com/v1/chat/completions", captured["url"])
        self.assertEqual("dots-secret-for-test", captured["headers"]["api-key"])
        self.assertNotIn("authorization", captured["headers"])
        self.assertEqual({
            "model": "dots3-note-prev",
            "messages": [{"role": "user", "content": "你好"}],
            "max_tokens": 321,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }, captured["payload"])
        self.assertEqual("更像真人的一句回应。", result.text)
        self.assertEqual({"provider": "dots", "model": "dots3-note-prev"}, result.provenance)

    async def test_dots_documented_root_base_gets_v1_path_and_thinking_can_be_enabled(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        env = {
            "DOTS_API_KEY": "dots-key",
            "DOTS_API_BASE": "https://note3-prev-api.askdiandian.com",
            "DOTS_ENABLE_THINKING": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await call_text([{"role": "user", "content": "test"}], provider="dots", client=client)
        self.assertEqual("https://note3-prev-api.askdiandian.com/v1/chat/completions", captured["url"])
        self.assertEqual({"enable_thinking": True}, captured["payload"]["chat_template_kwargs"])

    async def test_deepseek_keeps_existing_bearer_and_thinking_contract(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "DeepSeek reply"}}]})

        env = {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "deepseek-secret-for-test",
            "DEEPSEEK_API_BASE": "https://deepseek.example",
            "DEEPSEEK_MODEL": "deepseek-v4-flash",
        }
        with patch.dict(os.environ, env, clear=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await call_text([{"role": "user", "content": "test"}], provider="deepseek", client=client)

        self.assertEqual("https://deepseek.example/chat/completions", captured["url"])
        self.assertEqual("Bearer deepseek-secret-for-test", captured["headers"]["authorization"])
        self.assertNotIn("api-key", captured["headers"])
        self.assertEqual({"type": "disabled"}, captured["payload"]["thinking"])
        self.assertNotIn("chat_template_kwargs", captured["payload"])
        self.assertEqual({"provider": "deepseek", "model": "deepseek-v4-flash"}, result.provenance)

    async def test_empty_provider_content_is_rejected(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
        )
        with patch.dict(os.environ, {"DOTS_API_KEY": "configured"}, clear=True):
            async with httpx.AsyncClient(transport=transport) as client:
                with self.assertRaises(ProviderResponseError):
                    await call_text([{"role": "user", "content": "test"}], provider="dots", client=client)


class LLMProviderSelectionTests(unittest.TestCase):
    def test_illegal_and_unconfigured_providers_fail_closed(self) -> None:
        from backend.llm_provider import provider_config

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(UnsupportedProviderError):
                provider_config("openai")
            with self.assertRaises(ProviderNotConfiguredError):
                # Configuration is resolved before any network client is opened.
                provider_config("dots")

    def test_public_status_has_only_provider_names(self) -> None:
        env = {
            "LLM_PROVIDER": "dots",
            "DOTS_API_KEY": "dots-secret-for-test",
            "DOTS_API_BASE": "https://private-dots.example/v1",
            "DOTS_MODEL": "private-dots-model",
            "DEEPSEEK_API_KEY": "deepseek-secret-for-test",
            "DEEPSEEK_API_BASE": "https://private-deepseek.example",
            "DEEPSEEK_MODEL": "private-deepseek-model",
        }
        with patch.dict(os.environ, env, clear=True):
            status = provider_status()
        self.assertEqual({
            "default": "dots",
            "current": "dots",
            "available": ["deepseek", "dots"],
        }, status)
        serialized = json.dumps(status)
        for private_value in env.values():
            if private_value not in {"dots"}:
                self.assertNotIn(private_value, serialized)

    def test_unconfigured_default_is_not_silently_replaced(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "dots", "DEEPSEEK_API_KEY": "configured"}, clear=True):
            self.assertEqual({
                "default": "dots", "current": None, "available": ["deepseek"],
            }, provider_status())


if __name__ == "__main__":
    unittest.main()
