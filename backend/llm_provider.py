"""Provider-neutral text generation for the Heart Journey runtime.

Credentials and endpoints remain server-side.  Callers select only one of the
allowlisted provider names and receive text plus internal provenance.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


ALLOWED_PROVIDERS = ("deepseek", "dots")
DEFAULT_PROVIDER = "deepseek"


class LLMProviderError(RuntimeError):
    """Base error for provider selection and response failures."""


class UnsupportedProviderError(LLMProviderError):
    """Raised when a request names a provider outside the fixed allowlist."""


class ProviderNotConfiguredError(LLMProviderError):
    """Raised when an allowlisted provider has no server-side credential."""


class ProviderResponseError(LLMProviderError):
    """Raised when a provider response has no usable assistant text."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    api_base: str
    model: str
    enable_thinking: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def provenance(self) -> dict[str, str]:
        return {"provider": self.name, "model": self.model}


@dataclass(frozen=True)
class LLMTextResult:
    text: str
    provider: str
    model: str

    @property
    def provenance(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model}


def _env_value(name: str, default: str) -> str:
    return str(os.getenv(name, default) or "").strip() or default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_provider_name(provider: str | None = None) -> str:
    name = str(provider if provider is not None else os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER)).strip().lower()
    if name not in ALLOWED_PROVIDERS:
        raise UnsupportedProviderError("unsupported LLM provider")
    return name


def provider_config(provider: str | None = None, *, require_configured: bool = True) -> ProviderConfig:
    name = normalize_provider_name(provider)
    if name == "deepseek":
        config = ProviderConfig(
            name=name,
            api_key=str(os.getenv("DEEPSEEK_API_KEY", "") or "").strip(),
            api_base=_env_value("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
            model=_env_value("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        )
    else:
        config = ProviderConfig(
            name=name,
            api_key=str(os.getenv("DOTS_API_KEY", "") or "").strip(),
            api_base=_env_value("DOTS_API_BASE", "https://note3-prev-api.askdiandian.com/v1"),
            model=_env_value("DOTS_MODEL", "dots3-note-prev"),
            enable_thinking=_env_flag("DOTS_ENABLE_THINKING", False),
        )
    if require_configured and not config.configured:
        raise ProviderNotConfiguredError("selected LLM provider is not configured")
    return config


def provider_status() -> dict[str, Any]:
    """Return public-safe provider names only; never credentials or endpoints."""
    try:
        default = normalize_provider_name()
    except UnsupportedProviderError:
        default = None
    available = [
        name for name in ALLOWED_PROVIDERS
        if provider_config(name, require_configured=False).configured
    ]
    return {
        "default": default,
        "current": default if default in available else None,
        "available": available,
    }


def _chat_completions_url(config: ProviderConfig) -> str:
    """Accept a documented base URL, a /v1 base, or the full endpoint."""
    base = config.api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if config.name == "dots":
        parsed = urlsplit(base)
        if parsed.path.rstrip("/") != "/v1" and not parsed.path.rstrip("/").endswith("/v1"):
            parsed = parsed._replace(path=f"{parsed.path.rstrip('/')}/v1")
            base = urlunsplit(parsed)
    return f"{base}/chat/completions"


def _request_parts(
    config: ProviderConfig,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> tuple[dict[str, str], dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if config.name == "dots":
        headers = {"Content-Type": "application/json", "api-key": config.api_key}
        payload["chat_template_kwargs"] = {"enable_thinking": config.enable_thinking}
    else:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"}
        payload["thinking"] = {"type": "disabled"}
    return headers, payload


async def call_text(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 500,
    provider: str | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = 60.0,
) -> LLMTextResult:
    """Call one configured provider and extract only assistant-visible text."""
    config = provider_config(provider)
    headers, payload = _request_parts(config, messages, max_tokens)

    async def request(active_client: httpx.AsyncClient) -> httpx.Response:
        return await active_client.post(
            _chat_completions_url(config),
            headers=headers,
            json=payload,
        )

    if client is None:
        async with httpx.AsyncClient(timeout=timeout) as active_client:
            response = await request(active_client)
    else:
        response = await request(client)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or [] if isinstance(data, dict) else []
    text = str(choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    if not text:
        raise ProviderResponseError("LLM provider returned no output text")
    return LLMTextResult(text=text, provider=config.name, model=config.model)
