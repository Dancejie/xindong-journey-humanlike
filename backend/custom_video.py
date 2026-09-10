"""Fail-closed, single-submission adapter for private custom-character portraits.

The gateway wire format follows the existing Fumin/Seedance adapter. This module
does not authorize spend or approve likeness: the caller reserves project budget
and records the user's approval before calling submit_video, then stores a
downloaded result as a candidate until the user has reviewed it.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, AsyncIterator
from urllib.parse import quote, urlsplit, urlunsplit

import httpx


DURATION_SECONDS = 10
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_VIDEO_BYTES = 24 * 1024 * 1024
_ID_RE = re.compile(r"[A-Za-z0-9_.-]{1,200}\Z")
# The owner explicitly selected Mini. The operator must supply this exact ID,
# and /v1/models must confirm it before any photo upload. Other versions are
# never silently substituted, even if another Seedance model is available.
REQUIRED_MODEL = "seedance-2.0-mini"


class VideoProviderError(RuntimeError):
    """Safe message: never include raw provider bodies, URLs or credentials."""

    def __init__(self, message: str, *, stage: str = "configuration", status_code: int | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.status_code = status_code


class VideoNotConfiguredError(VideoProviderError):
    pass


class VideoSubmissionUncertainError(VideoProviderError):
    """A generation may exist remotely; hold the reservation, do not resubmit."""

    def __init__(self, message: str, *, status_code: int | None = None, job_id: str | None = None) -> None:
        super().__init__(message, stage="submit", status_code=status_code)
        self.job_id = job_id


class VideoCandidateValidationError(VideoProviderError):
    pass


@dataclass(frozen=True)
class _Config:
    key: str
    model: str
    base_url: str
    unit_cost: Decimal
    budget: Decimal
    download_hosts: frozenset[str]
    audio: bool


def _positive_decimal(name: str) -> Decimal:
    label = "本批新增视频预算" if name == "CUSTOM_VIDEO_BUDGET_CNY" else "动态形象的单次费用"
    try:
        value = Decimal(os.environ.get(name, ""))
    except InvalidOperation as exc:
        raise VideoNotConfiguredError(f"{label}尚未确认，暂不提交付费任务。") from exc
    if not value.is_finite() or value <= 0:
        raise VideoNotConfiguredError(f"{label}必须是已确认的正数，暂不提交付费任务。")
    return value


def _https_url(value: str) -> tuple[Any, str]:
    try:
        parts = urlsplit(value)
        hostname = (parts.hostname or "").lower().rstrip(".")
        if (
            parts.scheme != "https" or not hostname or parts.username or parts.password
            or parts.port not in {None, 443} or parts.fragment
            or any(character.isspace() for character in value)
        ):
            raise ValueError("invalid URL")
        hostname = hostname.encode("idna").decode("ascii")
    except (ValueError, UnicodeError) as exc:
        raise VideoCandidateValidationError("媒体地址不符合安全要求。", stage="url-validation") from exc
    return parts, hostname


def _configuration(*, for_submission: bool = True) -> _Config:
    key = os.environ.get("CUSTOM_VIDEO_API_KEY") or os.environ.get("FUMIN_API_KEY", "")
    model = os.environ.get("CUSTOM_VIDEO_MODEL", "").strip()
    if not key or not model or "seedance" not in model.lower() or not _ID_RE.fullmatch(model):
        raise VideoNotConfiguredError("动态形象生成尚未启用；管理员需配置指定的 Seedance 2.0 Mini 模型和凭据。")
    if for_submission and model != REQUIRED_MODEL:
        raise VideoNotConfiguredError("动态形象需要 Seedance 2.0 Mini；当前配置不匹配，不会改用完整版、Fast 或其他版本。")
    base = os.environ.get("CUSTOM_VIDEO_BASE_URL", "https://fumin.ai").rstrip("/")
    try:
        parts, _ = _https_url(base)
    except VideoProviderError as exc:
        raise VideoNotConfiguredError("动态形象服务地址配置无效。") from exc
    if parts.path or parts.query:
        raise VideoNotConfiguredError("动态形象服务地址必须是 HTTPS 根地址。")
    # A cap being lowered/disabled must not hide a job already paid for. Only
    # submission checks authorizations; owner-authorized read calls can recover
    # an existing task without opening permission to create another one.
    cost = _positive_decimal("CUSTOM_VIDEO_UNIT_COST_CNY") if for_submission else Decimal(0)
    budget = _positive_decimal("CUSTOM_VIDEO_BUDGET_CNY") if for_submission else Decimal(0)
    if for_submission:
        if budget < cost:
            raise VideoNotConfiguredError("项目预算不足以生成一段动态形象。")
        if budget > 200 and not os.environ.get("CUSTOM_VIDEO_BUDGET_APPROVAL", "").strip():
            raise VideoNotConfiguredError("项目预算超过 ¥200，须先记录人工批准的新增上限。")
    hosts: set[str] = set()
    for value in os.environ.get("CUSTOM_VIDEO_DOWNLOAD_HOSTS", "").split(","):
        value = value.strip().lower()
        if not value:
            continue
        if "*" in value or any(c in value for c in "/:@?#") or value.endswith("."):
            raise VideoNotConfiguredError("动态形象下载域名必须是精确域名，不能使用通配符。")
        try:
            hosts.add(value.encode("idna").decode("ascii"))
        except UnicodeError as exc:
            raise VideoNotConfiguredError("动态形象下载域名配置无效。") from exc
    if not hosts:
        raise VideoNotConfiguredError("尚未配置动态形象的可信下载域名。")
    if for_submission and not shutil.which("ffprobe"):
        raise VideoNotConfiguredError("服务器尚未安装视频校验工具，暂不生成付费视频。")
    return _Config(key, model, base, cost, budget, frozenset(hosts), os.environ.get("CUSTOM_VIDEO_GENERATE_AUDIO") == "true")


def config_status() -> dict[str, Any]:
    """Public configuration summary; never disclose endpoints or credentials."""
    spec = {"durationSeconds": DURATION_SECONDS, "resolution": "480p", "modelLabel": "Seedance 2.0 Mini", "autoSubmit": True}
    try:
        config = _configuration()
    except VideoProviderError as exc:
        return {**spec, "available": False, "estimatedCostCny": None, "reason": str(exc)}
    return {**spec, "available": True, "estimatedCostCny": float(config.unit_cost)}


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bound_spec(director: dict[str, Any]) -> dict[str, Any]:
    return {key: director.get(key) for key in ("requestedModel", "usedModel", "prompt", "photoSha256", "ratio", "durationSeconds", "resolution", "watermark", "generateAudio")}


def build_director_card(card: dict[str, Any], photo_hash: str) -> dict[str, Any]:
    """Only identity reference and adult age enter media generation, not PII/preferences."""
    if not re.fullmatch(r"[a-f0-9]{64}", photo_hash):
        raise ValueError("photo_hash must be a SHA-256 digest")
    identity = card.get("identity") if isinstance(card.get("identity"), dict) else card
    profile_facts = (card.get("sourceProfile") or {}).get("facts", {})
    age = identity.get("age", profile_facts.get("age", 25))
    if isinstance(age, bool) or not isinstance(age, int) or not 18 <= age <= 100:
        raise ValueError("Custom video requires an adult declared age")
    character_id = str(card.get("characterId") or card.get("id") or "custom-player")
    if not _ID_RE.fullmatch(character_id):
        character_id = "custom-player"
    audio = os.environ.get("CUSTOM_VIDEO_GENERATE_AUDIO") == "true"
    audio_direction = "仅轻柔海风、远处真实海浪和细微衣物摩擦声，无对白、无旁白、无配乐，不模仿或克隆声音。" if audio else "无音轨、无对白、无旁白，不做说话口型，不克隆声音。"
    prompt = (
        "10秒真人写实动态人物海报，移动端竖屏9:16、480p，单一人物、单一连续镜头。"
        "场景为傍晚海岛别墅门廊，浅暖自然侧光，身后门灯和远处海面柔焦。"
        f"唯一主角是参考照片中的同一位成年人物，用户声明年龄{age}岁；"
        "严格保留参考图的脸部轮廓、五官比例、肤色、发型、体态与年龄感，不美型成其他人，不改变性别表达。"
        "保留参考照片的日常衣装；不复制图片中的文字、边框、其他人物或室内背景。"
        "0–2秒：胸部以上中近景，人物已站稳，自然呼吸，肩部放松，视线略落在镜头旁，给观众认清面孔的时间。"
        "2–5秒：视线平缓转向镜头，自然眨眼，嘴角慢慢有一点开心的微笑；动作不夸张，不张嘴大笑，不摆手势。"
        "5–9秒：保持温和目光接触，微笑自然放松，只有轻微呼吸和发丝随海风动，固定机位仅极轻地向前推进。"
        "9–10秒：镜头停止推进，保持同一姿态与轻微笑意，尾部稳定不少于1秒；不突然转场、复位或走出画面。"
        "脸在画面中央偏上但不贴顶，顶部留12%和底部留28%界面安全区，完整显示头部和肩膀，皮肤质感真实。"
        + audio_direction +
        "禁止磨皮塑料脸、卡通化、身份漂移、多人、手部特写、畸形五官、人物分身、快速推拉、镜头抖动、假文字、字幕、Logo与新增水印。"
    )
    model = os.environ.get("CUSTOM_VIDEO_MODEL", "").strip() or None
    director: dict[str, Any] = {
        "assetId": f"{character_id}--custom-introduction--portrait-001",
        "runtimeTrigger": "custom-character.approved",
        "identityScope": "single", "cast": [character_id],
        "sourceRefs": [{"role": "identity", "sha256": photo_hash, "payloadRole": "reference_image", "intendedTransfer": ["face", "hair", "body", "wardrobe"], "forbiddenTransfer": ["otherPeople", "text", "background"]}],
        "stateIn": "主角站在门廊，肩膀放松，视线略在镜头旁",
        "actionContract": "视线转向镜头后自然轻微微笑",
        "stateOut": {"oneVisibleDelta": "与镜头建立温和目光接触", "stableTailSeconds": 1},
        "audioContract": audio_direction,
        "fallback": "user-uploaded-normalized-portrait",
        "requestedModel": model, "usedModel": model,
        "photoSha256": photo_hash, "prompt": prompt,
        "ratio": "9:16", "durationSeconds": DURATION_SECONDS, "resolution": "480p",
        "watermark": False, "generateAudio": audio, "doNotSubmit": True,
    }
    director["specHash"] = _canonical_hash(_bound_spec(director))
    return director


def _validate_approval(photo: bytes, director: dict[str, Any], config: _Config) -> None:
    if not photo or len(photo) > MAX_PHOTO_BYTES or not photo.startswith(b"\xff\xd8\xff"):
        raise VideoProviderError("请先提供经过校验、去除元数据的 JPEG 形象照。", stage="approval")
    photo_hash = hashlib.sha256(photo).hexdigest()
    spec_hash = _canonical_hash(_bound_spec(director))
    approval = director.get("approval")
    if not isinstance(approval, dict):
        approval = {}
    try:
        approved_cost = Decimal(str(approval.get("maxCostCny", "")))
        reviewed_at = datetime.fromisoformat(str(approval.get("reviewedAt", "")))
        valid_time = reviewed_at.tzinfo is not None and reviewed_at.utcoffset() is not None
    except (InvalidOperation, ValueError):
        approved_cost, valid_time = Decimal(0), False
    valid = (
        director.get("doNotSubmit") is False and approval.get("confirmed") is True
        and director.get("specHash") == spec_hash == approval.get("specHash")
        and director.get("photoSha256") == photo_hash == approval.get("referenceHash")
        and director.get("requestedModel") == config.model == director.get("usedModel")
        and director.get("ratio") == "9:16" and director.get("resolution") == "480p"
        and director.get("durationSeconds") == DURATION_SECONDS and director.get("watermark") is False
        and director.get("generateAudio") == config.audio
        and isinstance(director.get("prompt"), str) and 1 <= len(director["prompt"]) <= 6000
        and approved_cost.is_finite() and approved_cost >= config.unit_cost
        and bool(str(approval.get("budgetRef", "")).strip()) and bool(str(approval.get("reviewer", "")).strip())
        and valid_time
    )
    if not valid:
        raise VideoProviderError("本次照片、模型、规格和费用尚未获得一致的生成确认。", stage="approval")


@asynccontextmanager
async def _client_scope(client: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
    if client is not None:
        yield client
    else:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10), follow_redirects=False, trust_env=False) as owned:
            yield owned


async def _request_json(client: httpx.AsyncClient, config: _Config, method: str, path: str, *, stage: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = await client.request(method, config.base_url + path, headers={"Authorization": f"Bearer {config.key}"}, follow_redirects=False, **kwargs)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
        if stage == "submit":
            raise VideoSubmissionUncertainError("生成请求结果尚不明确，请保留本次记录核对，勿重复提交。") from exc
        raise VideoProviderError("视频服务暂时无法连接，请稍后查询已有任务。", stage=stage) from exc
    if not 200 <= response.status_code < 300:
        if stage == "submit" and response.status_code not in {400, 401, 403, 404, 405, 413, 415, 422}:
            raise VideoSubmissionUncertainError("生成请求未得到确定结果，请核对本次任务，勿重复提交。", status_code=response.status_code)
        raise VideoProviderError("视频服务未接受本次请求。", stage=stage, status_code=response.status_code)
    try:
        payload = response.json() if len(response.content) <= 512 * 1024 else None
    except (ValueError, UnicodeError):
        payload = None
    if not isinstance(payload, dict):
        if stage == "submit":
            raise VideoSubmissionUncertainError("生成服务返回不完整，请核对本次任务，勿重复提交。")
        raise VideoProviderError("视频服务响应不完整。", stage=stage)
    return payload


def _model_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        if isinstance(value.get("id"), str):
            found.add(value["id"])
        for nested in value.values():
            found.update(_model_ids(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_model_ids(nested))
    return found


async def submit_video(photo_bytes: bytes, director: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> str:
    """Submit at most one generation request; caller must reserve budget first."""
    config = _configuration()
    _validate_approval(photo_bytes, director, config)
    async with _client_scope(client) as session:
        models = await _request_json(session, config, "GET", "/v1/models", stage="probe")
        if config.model not in _model_ids(models):
            raise VideoProviderError("指定的 Seedance 模型当前不可用，未上传照片或切换模型。", stage="probe")
        uploaded = await _request_json(session, config, "POST", "/api/v3/files/uploads", stage="upload", files={"file": ("identity.jpg", photo_bytes, "image/jpeg")})
        file_id = str(uploaded.get("id") or "")
        if not _ID_RE.fullmatch(file_id):
            raise VideoProviderError("照片上传未返回可用的文件编号，未提交视频生成。", stage="upload")
        info = await _request_json(session, config, "GET", f"/api/v3/files/{quote(file_id, safe='')}", stage="upload")
        image_url = info.get("url") or uploaded.get("url")
        if not isinstance(image_url, str):
            raise VideoProviderError("照片上传未返回有效地址，未提交视频生成。", stage="upload")
        _https_url(image_url)
        payload = {
            "model": config.model,
            "content": [{"type": "text", "text": director["prompt"]}, {"type": "image_url", "image_url": {"url": image_url}, "role": "reference_image"}],
            "generate_audio": config.audio, "ratio": "9:16", "duration": DURATION_SECONDS, "resolution": "480p", "watermark": False,
        }
        created = await _request_json(session, config, "POST", "/api/v3/contents/generations/tasks", stage="submit", json=payload)
        task_id = str(created.get("id") or "")
        if not _ID_RE.fullmatch(task_id):
            raise VideoSubmissionUncertainError("生成请求未返回任务编号，请核对本次记录，勿重复提交。")
        if created.get("model") not in {None, config.model}:
            raise VideoSubmissionUncertainError("服务返回的模型与批准模型不一致，请人工核对。", job_id=task_id)
        return task_id


def _video_url(value: Any) -> str | None:
    if isinstance(value, dict):
        if isinstance(value.get("video_url"), str):
            return value["video_url"]
        for nested in value.values():
            result = _video_url(nested)
            if result:
                return result
    elif isinstance(value, list):
        for nested in value:
            result = _video_url(nested)
            if result:
                return result
    return None


async def poll_video(job_id: str, *, expected_model: str | None = None, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """A read-only lookup. The internal result must not be sent directly to UI."""
    if not _ID_RE.fullmatch(job_id):
        raise VideoProviderError("视频任务编号无效。", stage="poll")
    config = _configuration(for_submission=False)
    if expected_model is not None:
        if not _ID_RE.fullmatch(expected_model) or "seedance" not in expected_model.lower():
            raise VideoCandidateValidationError("任务的已批准模型记录无效。", stage="poll")
        config = replace(config, model=expected_model)
    async with _client_scope(client) as session:
        payload = await _request_json(session, config, "GET", f"/api/v3/contents/generations/tasks/{quote(job_id, safe='')}", stage="poll")
    if payload.get("model") not in {None, config.model}:
        raise VideoCandidateValidationError("任务模型与当前指定模型不一致，候选未启用。", stage="poll")
    status = str(payload.get("status") or "")
    if status in {"queued", "running", "processing", "submitted", "pending"}:
        status = "processing"
    if status not in {"processing", "succeeded", "failed", "cancelled", "expired"}:
        raise VideoProviderError("视频任务状态尚不明确，请稍后查询，不要重新提交。", stage="poll")
    result: dict[str, Any] = {"status": status, "requestedModel": config.model, "usedModel": payload.get("model")}
    if status == "succeeded":
        url = _video_url(payload)
        if not url:
            raise VideoCandidateValidationError("任务完成但没有返回可校验的视频地址。", stage="poll")
        _, host = _https_url(url)
        if host not in config.download_hosts:
            raise VideoCandidateValidationError("生成视频的来源不在可信下载域名清单中。", stage="poll")
        result["video_url"] = url
    return result


async def _resolve_public_address(host: str) -> str:
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise VideoProviderError("视频下载地址暂时无法解析。", stage="download") from exc
    ips = {entry[4][0] for entry in addresses}
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise VideoCandidateValidationError("视频下载地址未通过公网安全校验。", stage="download")
    return sorted(ips)[0]


def _validate_expected_duration(expected_duration_seconds: int) -> None:
    # Recover only known historical specs. The saved director, never user input,
    # supplies 5 for a job submitted before the 10-second portrait change.
    if isinstance(expected_duration_seconds, bool) or not isinstance(expected_duration_seconds, int) or expected_duration_seconds not in {5, DURATION_SECONDS}:
        raise VideoCandidateValidationError("任务记录中的视频时长不在支持的规格内。", stage="validation")


def _validate_candidate_bytes(data: bytes, expected_duration_seconds: int = DURATION_SECONDS) -> None:
    _validate_expected_duration(expected_duration_seconds)
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise VideoCandidateValidationError("生成结果不是有效的 MP4 文件。", stage="validation")
    executable = shutil.which("ffprobe")
    if not executable:
        raise VideoCandidateValidationError("视频校验工具不可用，候选未启用。", stage="validation")
    # Temporary file is always removed, including failure and timeout paths.
    with tempfile.NamedTemporaryFile(prefix="xindong-custom-video-", suffix=".mp4") as handle:
        handle.write(data)
        handle.flush()
        try:
            probe = subprocess.run([executable, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries", "format=duration:stream=codec_name,codec_type,width,height,pix_fmt", "-of", "json", handle.name], check=True, capture_output=True, text=True, timeout=20)
            metadata = json.loads(probe.stdout)
            duration = float(metadata["format"]["duration"])
            videos = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
            video = videos[0] if len(videos) == 1 else {}
            width, height = int(video.get("width", 0)), int(video.get("height", 0))
            # Mini's verified 480p output can be padded to 496x864. Retain
            # standard historical sizes, but do not admit arbitrary sizes above
            # 480 pixels wide: the only extension (and absolute cap) is 496x864.
            valid_dimensions = (320 <= width <= 480 and 560 <= height <= 864) or (width, height) == (496, 864)
            valid = (expected_duration_seconds - 0.5 <= duration <= expected_duration_seconds + 0.5 and video.get("codec_name") == "h264" and video.get("pix_fmt") in {"yuv420p", "yuvj420p"} and valid_dimensions and abs(width / height - 9 / 16) < 0.02)
        except (subprocess.SubprocessError, ValueError, KeyError, TypeError, ZeroDivisionError, OSError) as exc:
            raise VideoCandidateValidationError("视频技术校验失败，候选未启用。", stage="validation") from exc
        if not valid:
            raise VideoCandidateValidationError(f"视频未达到 {expected_duration_seconds} 秒、480p 竖屏 H.264 的约定规格。", stage="validation")


async def download_candidate(video_url: str, *, expected_duration_seconds: int = DURATION_SECONDS, client: httpx.AsyncClient | None = None) -> bytes:
    """Fetch approved-host HTTPS bytes without auth, redirects or DNS rebinding."""
    _validate_expected_duration(expected_duration_seconds)
    config = _configuration(for_submission=False)
    parts, host = _https_url(video_url)
    if host not in config.download_hosts:
        raise VideoCandidateValidationError("视频来源不在可信下载清单中。", stage="download")
    address = await _resolve_public_address(host)
    # Pin this connection to the address just validated. Keep original TLS SNI
    # and Host so certificate verification and signed CDN URLs continue to work.
    authority = f"[{address}]" if ":" in address else address
    pinned_url = urlunsplit(("https", authority, parts.path, parts.query, ""))
    async with _client_scope(client) as session:
        try:
            async with session.stream("GET", pinned_url, headers={"Host": host, "Accept": "video/mp4", "Accept-Encoding": "identity"}, extensions={"sni_hostname": host}, follow_redirects=False, timeout=httpx.Timeout(90, connect=10)) as response:
                if response.status_code != 200:
                    raise VideoProviderError("视频下载失败或发生跳转，候选未启用。", stage="download", status_code=response.status_code)
                if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "video/mp4":
                    raise VideoCandidateValidationError("下载内容不是 MP4 视频。", stage="validation")
                if response.headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
                    raise VideoCandidateValidationError("视频使用了未经允许的传输压缩。", stage="validation")
                content_length = response.headers.get("content-length")
                if content_length and (not content_length.isdigit() or int(content_length) > MAX_VIDEO_BYTES):
                    raise VideoCandidateValidationError("视频超过 24 MB 大小限制。", stage="validation")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_VIDEO_BYTES:
                        raise VideoCandidateValidationError("视频超过 24 MB 大小限制。", stage="validation")
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            raise VideoProviderError("视频下载暂时中断，请查询原任务，不要重新生成。", stage="download") from exc
    candidate = bytes(data)
    await asyncio.to_thread(_validate_candidate_bytes, candidate, expected_duration_seconds)
    return candidate
