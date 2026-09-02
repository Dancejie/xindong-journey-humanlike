#!/usr/bin/env python3
"""Derive lightweight gender-specific R9 selection placeholders from approved MBTI pair art.

These files are UI concept anchors only.  They are not identity masters and
must never be supplied to Seedance as a person-identity reference.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(
    "/Users/dangsijie/Documents/回声剧场/心动之旅-MBTI-QQ小人/v5-16型独立双人卡"
)
SOURCE_MANIFEST = SOURCE_DIR / "media-manifest.json"
OUTPUT_DIR = ROOT / "frontend/public/media/selection-anchors"
OUTPUT_MANIFEST = ROOT / "media/production/full-mbti-r9/selection-anchor-manifest.json"

SPECS = (
    ("ENTJ", "03-ENTJ-紫人双人卡.png", "shaozheng", "qince"),
    ("ENTP", "04-ENTP-紫人双人卡.png", "jiheng", "xiache"),
    ("INFP", "06-INFP-绿人双人卡.png", "zhouyan", "ningzhi"),
    ("ENFJ", "07-ENFJ-绿人双人卡.png", "xuhang", "gutang"),
    ("ISTJ", "09-ISTJ-蓝人双人卡.png", "yanxu", "jianning"),
    ("ESTJ", "11-ESTJ-蓝人双人卡.png", "luozheng", "chengqing"),
    ("ISFP", "14-ISFP-黄人双人卡.png", "xiemu", "yaoyin"),
    ("ESFP", "16-ESFP-黄人双人卡.png", "hanxi", "luoxing"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required")
    source_root = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    source_assets = {item["file"]: item for item in source_root["assets"]}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, object]] = []
    for mbti, filename, male_id, female_id in SPECS:
        source_path = SOURCE_DIR / filename
        expected = source_assets.get(filename)
        if not expected or expected.get("sha256") != sha256(source_path):
            raise SystemExit(f"approved source hash mismatch: {filename}")
        for gender, character_id, x in (("男性", male_id, 0), ("女性", female_id, 768)):
            output_path = OUTPUT_DIR / f"{character_id}.jpg"
            subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_path),
                    "-vf", f"crop=768:1024:{x}:0,scale=480:640:flags=lanczos",
                    "-frames:v", "1", "-q:v", "2", str(output_path),
                ],
                check=True,
            )
            outputs.append({
                "characterId": character_id,
                "mbti": mbti,
                "gender": gender,
                "runtimePath": f"/media/selection-anchors/{character_id}.jpg",
                "sha256": sha256(output_path),
                "dimensions": {"width": 480, "height": 640},
                "sourceFile": filename,
                "sourceSha256": expected["sha256"],
                "crop": {"x": x, "y": 0, "width": 768, "height": 1024},
                "status": "derived-concept-anchor",
                "usage": ["mbti-selection-placeholder", "role-selection-placeholder"],
                "identityReference": False,
                "seedanceIdentityReferenceAllowed": False,
            })
    manifest = {
        "schemaVersion": "full-mbti-r9/selection-anchor-manifest-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "internal-reference-only-not-runtime-identity",
        "source": {
            "path": str(SOURCE_DIR),
            "manifestPath": str(SOURCE_MANIFEST),
            "manifestSha256": sha256(SOURCE_MANIFEST),
            "qaStatus": source_root.get("status"),
        },
        "rights": {
            "status": "reference-only-internal",
            "publicReleaseCleared": False,
            "claimBoundary": "Derived from the user-approved QQ pair-card art; not a realistic person identity or a cleared Seedance identity reference.",
        },
        "assets": outputs,
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"built {len(outputs)} selection placeholders -> {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
