"""Load ignored local LLM settings without logging credential values."""
from __future__ import annotations

import os
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def load_local_llm_env(root: Path, explicit_file: str | None = None) -> None:
    """Layer legacy DeepSeek then current LLM files; exported env stays highest priority."""
    legacy_path = root / ".env.deepseek.local"
    values = _read_env_file(legacy_path)

    selected = explicit_file or os.getenv("LLM_ENV_FILE", "").strip()
    if selected:
        current_path = Path(selected).expanduser()
        if not current_path.is_file():
            raise FileNotFoundError("LLM env file is not readable")
    else:
        current_path = root / ".env.llm.local"

    if current_path != legacy_path:
        values.update(_read_env_file(current_path))

    # Preserve variables deliberately exported by the caller while still
    # allowing .env.llm.local to override values loaded from the legacy file.
    for key, value in values.items():
        os.environ.setdefault(key, value)
