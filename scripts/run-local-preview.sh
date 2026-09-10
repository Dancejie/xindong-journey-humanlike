#!/bin/zsh
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/.local-runtime"
PG_ISREADY_BIN="${PG_ISREADY_BIN:-$(command -v pg_isready || true)}"
PG_CTL_BIN="${PG_CTL_BIN:-$(command -v pg_ctl || true)}"

if [[ -z "$PG_ISREADY_BIN" || -z "$PG_CTL_BIN" ]]; then
  echo "PostgreSQL tools not found. Add pg_isready and pg_ctl to PATH, or set PG_ISREADY_BIN and PG_CTL_BIN." >&2
  exit 1
fi

cd "$PROJECT_DIR"
export LANG="C.UTF-8"
export LC_ALL="C.UTF-8"

# launchd does not inherit the interactive shell's Homebrew PATH. Reuse the
# installed media validator so enabling video cannot fail solely under launchd.
if ! command -v ffprobe >/dev/null 2>&1; then
  for custom_video_bin_dir in /opt/homebrew/bin /usr/local/bin; do
    if [[ -x "$custom_video_bin_dir/ffprobe" ]]; then
      export PATH="$custom_video_bin_dir:$PATH"
      break
    fi
  done
  unset custom_video_bin_dir
fi

if ! "$PG_ISREADY_BIN" -h 127.0.0.1 -p 5432 -q; then
  "$PG_CTL_BIN" -D "$RUNTIME_DIR/postgres" -l "$RUNTIME_DIR/postgres.log" start
fi

LEGACY_LLM_ENV_PATH="${DEEPSEEK_ENV_FILE:-$PROJECT_DIR/.env.deepseek.local}"
LLM_ENV_PATH=""
if [[ -n "${DEEPSEEK_ENV_FILE:-}" && ! -r "$LEGACY_LLM_ENV_PATH" ]]; then
  echo "DEEPSEEK_ENV_FILE does not point to a readable file." >&2
  exit 1
fi
if [[ -n "${LLM_ENV_FILE:-}" ]]; then
  LLM_ENV_PATH="$LLM_ENV_FILE"
  if [[ ! -r "$LLM_ENV_PATH" ]]; then
    echo "LLM_ENV_FILE does not point to a readable file." >&2
    exit 1
  fi
elif [[ -f "$PROJECT_DIR/.env.llm.local" ]]; then
  LLM_ENV_PATH="$PROJECT_DIR/.env.llm.local"
fi

if [[ -f "$LEGACY_LLM_ENV_PATH" || -n "$LLM_ENV_PATH" ]]; then
  set -a
  # Keep an existing DeepSeek setup available for A/B comparison, then let the
  # current provider file add or override values without copying the old key.
  if [[ -f "$LEGACY_LLM_ENV_PATH" ]]; then
    source "$LEGACY_LLM_ENV_PATH"
  fi
  if [[ -n "$LLM_ENV_PATH" && "$LLM_ENV_PATH" != "$LEGACY_LLM_ENV_PATH" ]]; then
    source "$LLM_ENV_PATH"
  fi
  set +a
else
  echo "No local LLM env file found; using already exported environment variables." >&2
fi

# Custom video uses the existing approved provider key without copying it into
# tracked sources. Its independently approved batch budget is never inherited
# from an older media job. This local file is ignored by git.
CUSTOM_VIDEO_ENV_PATH="${CUSTOM_VIDEO_ENV_FILE:-$PROJECT_DIR/.env.custom-video.local}"
if [[ -r "$CUSTOM_VIDEO_ENV_PATH" ]]; then
  set -a
  source "$CUSTOM_VIDEO_ENV_PATH"
  set +a
fi
if [[ -z "${CUSTOM_VIDEO_API_KEY:-}" && -n "${CUSTOM_VIDEO_CREDENTIALS_FILE:-}" ]]; then
  if [[ -r "$CUSTOM_VIDEO_CREDENTIALS_FILE" ]]; then
    custom_video_credentials_mode=$(stat -f '%Lp' "$CUSTOM_VIDEO_CREDENTIALS_FILE" 2>/dev/null || stat -c '%a' "$CUSTOM_VIDEO_CREDENTIALS_FILE" 2>/dev/null || true)
    if [[ "$custom_video_credentials_mode" == "600" || "$custom_video_credentials_mode" == "400" ]]; then
      # Parse only the key, never execute a shared credential file as shell.
      if { while IFS='=' read -r custom_video_key_name custom_video_key_value || [[ -n "$custom_video_key_name$custom_video_key_value" ]]; do
        if [[ "$custom_video_key_name" == "FUMIN_API_KEY" ]]; then
          custom_video_key_value="${custom_video_key_value%$'\r'}"
          custom_video_key_value="${custom_video_key_value#\"}"
          custom_video_key_value="${custom_video_key_value%\"}"
          custom_video_key_value="${custom_video_key_value#\'}"
          custom_video_key_value="${custom_video_key_value%\'}"
          export CUSTOM_VIDEO_API_KEY="$custom_video_key_value"
        fi
      done < "$CUSTOM_VIDEO_CREDENTIALS_FILE"; } 2>/dev/null; then
        :
      else
        echo "Custom video credentials could not be read; photo-based play remains enabled." >&2
      fi
      unset custom_video_key_name custom_video_key_value
    else
      echo "Custom video credentials require file mode 600 or 400; video stays unavailable." >&2
    fi
  else
    echo "Custom video credentials are unavailable; photo-based play remains enabled." >&2
  fi
fi
export APP_AUTH_MODE=public
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@127.0.0.1:5432/cowork_dev}"
# Local playtesting opens character chats and contextual scene generation much
# more frequently than a public visitor. Keep Render's 20/200 abuse guard
# unchanged, while giving the single-user local preview enough room for a full
# session. Either value can still be overridden from .env.llm.local.
export AGENT_RATE_LIMIT="${AGENT_RATE_LIMIT:-80}"
export AGENT_GLOBAL_RATE_LIMIT="${AGENT_GLOBAL_RATE_LIMIT:-400}"

exec "${PYTHON_BIN:-$RUNTIME_DIR/venv/bin/python}" -m uvicorn backend.app:app --host 127.0.0.1 --port "${PORT:-4184}"
