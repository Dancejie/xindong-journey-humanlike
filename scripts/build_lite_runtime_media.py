#!/usr/bin/env python3
"""Build and verify the mobile-lite Heart Journey runtime video set.

The script is deliberately split into three phases:

1. ``prepare`` transcodes every runtime MP4 into an ignored work directory.
2. ``apply`` verifies every source/output hash, keeps exact source backups, then
   atomically promotes the lightweight derivatives and refreshes the runtime
   manifest.
3. ``verify`` checks the promoted files, manifest bindings and optional full
   decode without touching media.

No network or generation provider is used. Audio presence and duration are
preserved; only the delivery encoding changes.
"""

from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
VIDEO_DIR = PUBLIC / "media" / "video"
WORK = ROOT / "frontend" / ".work-lite-media-r10"
STAGED_VIDEO_DIR = WORK / "video"
BACKUP_VIDEO_DIR = WORK / "masters" / "video"
STAGING_REPORT = WORK / "staging-report.json"
FINAL_REPORT = ROOT / "qa" / "LITE-RUNTIME-MEDIA-R10.json"
RUNTIME_MANIFEST = ROOT / "media" / "runtime-media-manifest.json"
PROFILE = "render-mobile-lite-r10"
TARGET_WIDTH = 360
TARGET_HEIGHT = 640
VIDEO_FILTER = (
    "scale=360:640:flags=lanczos:force_original_aspect_ratio=increase:"
    "force_divisible_by=2,crop=360:640,setsar=1"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def probe(path: Path) -> dict[str, Any]:
    payload = json.loads(
        run([
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path),
        ]).stdout
    )
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    videos = [item for item in streams if item.get("codec_type") == "video"]
    audios = [item for item in streams if item.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise RuntimeError(f"expected exactly one video stream: {path}")
    video = videos[0]
    duration = float((payload.get("format") or {}).get("duration") or video.get("duration") or 0)
    frame_rate = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    numerator, denominator = (frame_rate.split("/", 1) + ["1"])[:2]
    fps = float(numerator) / max(float(denominator), 1.0)
    audio = audios[0] if audios else {}
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "codec": str(video.get("codec_name") or ""),
        "pixelFormat": str(video.get("pix_fmt") or ""),
        "frameRate": round(fps, 6),
        "duration": round(duration, 6),
        "audioStreams": len(audios),
        "audioCodec": str(audio.get("codec_name") or "") or None,
        "audioSampleRate": int(audio.get("sample_rate") or 0) or None,
        "audioChannels": int(audio.get("channels") or 0),
        "bytes": path.stat().st_size,
    }


def faststart(path: Path) -> bool:
    with path.open("rb") as handle:
        payload = handle.read(min(path.stat().st_size, 4 * 1024 * 1024))
    moov = payload.find(b"moov")
    mdat = payload.find(b"mdat")
    return moov >= 0 and mdat >= 0 and moov < mdat


def runtime_inventory() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_json(RUNTIME_MANIFEST)
    assets = [item for item in manifest.get("assets", []) if isinstance(item, dict)]
    by_path = {
        str(item.get("path") or ""): item
        for item in assets
        if str(item.get("path") or "").endswith(".mp4")
    }
    disk_paths = {
        f"/media/video/{path.name}"
        for path in VIDEO_DIR.glob("*.mp4")
        if path.is_file()
    }
    if set(by_path) != disk_paths:
        raise RuntimeError(
            "runtime/disk MP4 inventory mismatch: "
            f"manifestOnly={sorted(set(by_path) - disk_paths)} "
            f"diskOnly={sorted(disk_paths - set(by_path))}"
        )
    if len(by_path) != 165:
        raise RuntimeError(f"expected 165 runtime MP4s, found {len(by_path)}")
    return manifest, by_path


def encode_one(runtime_path: str) -> dict[str, Any]:
    source = PUBLIC / runtime_path.removeprefix("/")
    target = STAGED_VIDEO_DIR / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    before = probe(source)
    source_sha = digest(source)
    command = [
        "ffmpeg", "-v", "error", "-y", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?", "-map_metadata", "-1",
        "-vf", VIDEO_FILTER,
        "-c:v", "libx264", "-preset", "medium", "-crf", "29",
        "-maxrate", "900k", "-bufsize", "1800k",
        "-profile:v", "high", "-level:v", "3.1", "-pix_fmt", "yuv420p",
        "-g", "48", "-keyint_min", "24", "-sc_threshold", "0",
        "-movflags", "+faststart",
    ]
    if before["audioStreams"]:
        command.extend(["-c:a", "aac", "-b:a", "72k", "-ac", "2", "-ar", "32000"])
    else:
        command.append("-an")
    command.append(str(target))
    run(command)
    after = probe(target)
    if (after["width"], after["height"]) != (TARGET_WIDTH, TARGET_HEIGHT):
        raise RuntimeError(f"unexpected dimensions for {runtime_path}: {after}")
    if after["codec"] != "h264" or after["pixelFormat"] != "yuv420p":
        raise RuntimeError(f"unexpected video codec for {runtime_path}: {after}")
    if after["audioStreams"] != before["audioStreams"]:
        raise RuntimeError(f"audio stream count changed for {runtime_path}")
    if before["audioStreams"] and after["audioCodec"] != "aac":
        raise RuntimeError(f"audio codec changed unexpectedly for {runtime_path}: {after}")
    if abs(float(after["duration"]) - float(before["duration"])) > 0.08:
        raise RuntimeError(f"duration drift for {runtime_path}: {before} -> {after}")
    run(["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"])
    if not faststart(target):
        raise RuntimeError(f"faststart failed for {runtime_path}")
    return {
        "runtimePath": runtime_path,
        "sourceSha256": source_sha,
        "runtimeSha256": digest(target),
        "source": before,
        "runtime": after,
        "reductionPercent": round((1 - after["bytes"] / before["bytes"]) * 100, 2),
        "faststart": True,
        "fullDecode": "passed",
    }


def prepare(workers: int) -> int:
    _, by_path = runtime_inventory()
    if WORK.exists():
        raise RuntimeError(f"work directory already exists; verify or clean it first: {WORK}")
    WORK.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(encode_one, path): path for path in sorted(by_path)}
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            path = futures[future]
            row = future.result()
            rows.append(row)
            print(f"[{index:03d}/165] {path}: {row['reductionPercent']:.2f}%", flush=True)
    rows.sort(key=lambda item: item["runtimePath"])
    source_bytes = sum(int(item["source"]["bytes"]) for item in rows)
    runtime_bytes = sum(int(item["runtime"]["bytes"]) for item in rows)
    report = {
        "schemaVersion": "heart-journey/lite-runtime-media-report-v1",
        "profile": PROFILE,
        "status": "prepared-not-applied",
        "preparedAt": now_iso(),
        "settings": {
            "dimensions": f"{TARGET_WIDTH}x{TARGET_HEIGHT}",
            "video": "H.264 high@3.1, yuv420p, CRF 29, maxrate 900k, faststart",
            "audio": "preserve presence; AAC 72k stereo 32kHz when present",
            "workers": workers,
            "paidGenerationCalls": 0,
        },
        "assetCount": len(rows),
        "sourceBytes": source_bytes,
        "runtimeBytes": runtime_bytes,
        "reclaimedBytes": source_bytes - runtime_bytes,
        "reductionPercent": round((1 - runtime_bytes / source_bytes) * 100, 2),
        "audioAssetCount": sum(1 for item in rows if item["runtime"]["audioStreams"]),
        "silentAssetCount": sum(1 for item in rows if not item["runtime"]["audioStreams"]),
        "assets": rows,
    }
    write_json(STAGING_REPORT, report)
    print(json.dumps({key: report[key] for key in ("status", "assetCount", "sourceBytes", "runtimeBytes", "reclaimedBytes", "reductionPercent", "audioAssetCount", "silentAssetCount")}, ensure_ascii=False, indent=2))
    return 0


def apply_staged() -> int:
    manifest, by_path = runtime_inventory()
    report = load_json(STAGING_REPORT)
    if report.get("profile") != PROFILE or report.get("status") != "prepared-not-applied":
        raise RuntimeError("staging report is not an unapplied R10 report")
    rows = [item for item in report.get("assets", []) if isinstance(item, dict)]
    if len(rows) != 165:
        raise RuntimeError(f"staging report must contain 165 assets, found {len(rows)}")
    for row in rows:
        runtime_path = str(row.get("runtimePath") or "")
        source = PUBLIC / runtime_path.removeprefix("/")
        staged = STAGED_VIDEO_DIR / source.name
        asset = by_path.get(runtime_path)
        if not asset:
            raise RuntimeError(f"staged path is not in manifest: {runtime_path}")
        if digest(source) != row.get("sourceSha256") or asset.get("sha256") != row.get("sourceSha256"):
            raise RuntimeError(f"source changed after prepare: {runtime_path}")
        if not staged.is_file() or digest(staged) != row.get("runtimeSha256"):
            raise RuntimeError(f"staged output changed after prepare: {runtime_path}")
    BACKUP_VIDEO_DIR.mkdir(parents=True, exist_ok=False)
    promoted: list[tuple[Path, Path]] = []
    try:
        for row in rows:
            runtime_path = str(row["runtimePath"])
            source = PUBLIC / runtime_path.removeprefix("/")
            staged = STAGED_VIDEO_DIR / source.name
            backup = BACKUP_VIDEO_DIR / source.name
            source.rename(backup)
            staged.rename(source)
            promoted.append((source, backup))
        for row in rows:
            runtime_path = str(row["runtimePath"])
            asset = by_path[runtime_path]
            source_meta = row["source"]
            runtime_meta = row["runtime"]
            asset["sourceMasterSha256"] = str(asset.get("sourceMasterSha256") or row["sourceSha256"])
            asset["sha256"] = row["runtimeSha256"]
            asset["dimensions"] = {"width": runtime_meta["width"], "height": runtime_meta["height"]}
            asset["duration"] = runtime_meta["duration"]
            asset["videoCodec"] = runtime_meta["codec"]
            asset["pixelFormat"] = runtime_meta["pixelFormat"]
            asset["frameRate"] = runtime_meta["frameRate"]
            audio = asset.get("audio") if isinstance(asset.get("audio"), dict) else {}
            audio["hasAudio"] = bool(runtime_meta["audioStreams"])
            audio["codec"] = runtime_meta["audioCodec"]
            audio["sampleRate"] = runtime_meta["audioSampleRate"]
            audio["channels"] = runtime_meta["audioChannels"]
            asset["audio"] = audio
            asset["runtimeDerivative"] = {
                "profile": PROFILE,
                "sourceSha256": row["sourceSha256"],
                "sourceDimensions": {"width": source_meta["width"], "height": source_meta["height"]},
                "sourceDuration": source_meta["duration"],
                "sourceBytes": source_meta["bytes"],
                "runtimeBytes": runtime_meta["bytes"],
                "runtimeSha256": row["runtimeSha256"],
                "encoding": report["settings"]["video"],
                "audioEncoding": report["settings"]["audio"],
                "visualContentChanged": False,
                "paidGenerationCalls": 0,
            }
        manifest["runtimeEncodingProfile"] = PROFILE
        manifest["runtimeEncodingReport"] = "qa/LITE-RUNTIME-MEDIA-R10.json"
        notes = manifest.get("notes") if isinstance(manifest.get("notes"), list) else []
        note = "R10 Lite keeps all 165 runtime clips and audio presence while replacing delivery copies with reviewed 360x640 H.264/AAC faststart derivatives."
        if note not in notes:
            notes.append(note)
        manifest["notes"] = notes
        write_json(RUNTIME_MANIFEST, manifest)
        report["status"] = "applied-runtime-integrated"
        report["appliedAt"] = now_iso()
        report["runtimeManifestSha256"] = digest(RUNTIME_MANIFEST)
        report["backupDirectory"] = "frontend/.work-lite-media-r10/masters/video"
        report["proofBoundary"] = "Delivery transcode only; it preserves runtime coverage and audio presence but does not expand rights clearance."
        write_json(FINAL_REPORT, report)
        write_json(STAGING_REPORT, report)
    except Exception:
        for source, backup in reversed(promoted):
            if source.exists():
                source.unlink()
            if backup.exists():
                backup.rename(source)
        raise
    print(json.dumps({key: report[key] for key in ("status", "assetCount", "sourceBytes", "runtimeBytes", "reclaimedBytes", "reductionPercent")}, ensure_ascii=False, indent=2))
    return 0


def verify(decode: bool) -> int:
    manifest, by_path = runtime_inventory()
    report = load_json(FINAL_REPORT)
    rows = [item for item in report.get("assets", []) if isinstance(item, dict)]
    failures: list[str] = []
    decoded = 0
    for row in rows:
        runtime_path = str(row.get("runtimePath") or "")
        path = PUBLIC / runtime_path.removeprefix("/")
        asset = by_path.get(runtime_path) or {}
        if not path.is_file():
            failures.append(f"missing {runtime_path}")
            continue
        actual_sha = digest(path)
        if actual_sha != row.get("runtimeSha256") or actual_sha != asset.get("sha256"):
            failures.append(f"hash mismatch {runtime_path}")
            continue
        try:
            media = probe(path)
            if (media["width"], media["height"]) != (TARGET_WIDTH, TARGET_HEIGHT):
                failures.append(f"dimension mismatch {runtime_path}")
            if media["codec"] != "h264" or media["pixelFormat"] != "yuv420p":
                failures.append(f"codec mismatch {runtime_path}")
            if media["audioStreams"] != int(row["runtime"]["audioStreams"]):
                failures.append(f"audio mismatch {runtime_path}")
            if not faststart(path):
                failures.append(f"faststart mismatch {runtime_path}")
            if decode:
                run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])
                decoded += 1
        except (OSError, ValueError, subprocess.CalledProcessError, RuntimeError) as error:
            failures.append(f"probe/decode failed {runtime_path}: {error}")
    result = {
        "verdict": "LITE_RUNTIME_MEDIA_PASS" if not failures else "LITE_RUNTIME_MEDIA_FAIL",
        "profile": manifest.get("runtimeEncodingProfile"),
        "assetCount": len(rows),
        "decoded": decoded,
        "runtimeBytes": sum((PUBLIC / str(row["runtimePath"]).removeprefix("/")).stat().st_size for row in rows if (PUBLIC / str(row["runtimePath"]).removeprefix("/")).is_file()),
        "failures": failures,
    }
    report["verdict"] = result["verdict"]
    report["lastVerifiedAt"] = now_iso()
    report["fullyDecoded"] = decoded
    report["verificationFailures"] = failures
    write_json(FINAL_REPORT, report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--workers", type=int, default=4)
    subparsers.add_parser("apply")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--decode", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("ffmpeg and ffprobe are required")
        return prepare(max(1, min(args.workers, 8)))
    if args.command == "apply":
        return apply_staged()
    if args.command == "verify":
        return verify(args.decode)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
