#!/usr/bin/env python3
"""Dry-run or apply the exact R10 Lite disposable-media cleanup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "frontend" / ".work-lite-media-r10"
REPORT = ROOT / "qa" / "LITE-RUNTIME-MEDIA-R10.json"
MANIFEST = ROOT / "media" / "runtime-media-manifest.json"
PUBLIC = ROOT / "frontend" / "public"
TEMP_FILES = [
    Path("/tmp/xindong-lite-sample-0.mp4"),
    Path("/tmp/xindong-lite-sample-1.mp4"),
    Path("/tmp/xindong-lite-sample-2.mp4"),
    Path("/tmp/xindong-lite-sample-3.mp4"),
    Path("/tmp/xindong-lite-sample-contact.jpg"),
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def tree_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def validate() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_path = {str(item.get("path") or ""): item for item in manifest.get("assets", [])}
    if report.get("status") != "applied-runtime-integrated":
        raise RuntimeError("R10 report is not applied")
    for row in report.get("assets", []):
        runtime_path = str(row.get("runtimePath") or "")
        runtime = PUBLIC / runtime_path.removeprefix("/")
        expected = str(row.get("runtimeSha256") or "")
        if not runtime.is_file() or digest(runtime) != expected:
            raise RuntimeError(f"runtime hash check failed: {runtime_path}")
        if (by_path.get(runtime_path) or {}).get("sha256") != expected:
            raise RuntimeError(f"manifest hash check failed: {runtime_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    validate()
    targets = [WORK, *TEMP_FILES]
    existing = [path for path in targets if path.exists()]
    reclaimable = sum(tree_bytes(path) for path in existing)
    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "targets": [str(path) for path in existing],
        "reclaimableBytes": reclaimable,
    }, ensure_ascii=False, indent=2))
    if not args.apply:
        return 0
    for path in existing:
        if path == WORK:
            shutil.rmtree(path)
        else:
            path.unlink()
    if any(path.exists() for path in existing):
        raise RuntimeError("one or more cleanup targets still exist")
    print(json.dumps({"verdict": "R10_LITE_CLEANUP_APPLIED", "reclaimedBytes": reclaimable}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
