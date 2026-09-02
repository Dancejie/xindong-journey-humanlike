#!/usr/bin/env python3
"""Validate the promoted R6 gender-rotation runtime media contract.

This validator is intentionally independent from the historical 25-file R4
gate.  R6 coverage means four approved event rotations for every authored
event plus the eight portraits promoted in that release. Later roster and
delivery-profile releases may add portraits or encode lightweight runtime
derivatives; those additions must not invalidate the historical R6 source
provenance contract.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
RUNTIME_PATH = ROOT / "media" / "runtime-media-manifest.json"
R6_DIR = ROOT / "media" / "production" / "gender-rotation-r6"
PLAN_PATH = R6_DIR / "manifest.r6.json"
ALLOWLIST_PATH = R6_DIR / "visual-qa-allowlist.r6.json"
PROMOTION_PATH = R6_DIR / "promotion-plan-applied.r6.json"
CARDS_PATH = ROOT / "content" / "character_cards.v3.json"

DAY1_ASSET_IDS = {
    "D1-A1-island-hotel-establish", "D1-A2-villa-entry",
    "D1-A3-cast-introductions", "D1-A3B-cast-first-impressions",
    "D1-A4-icebreaker-selection", "D1-A5-guided-smalltalk",
    "D1-A6-first-dinner-team", "D1-A7-heart-message",
    "D2-A1-memory-callback",
}
STORY_ASSET_IDS = {
    "EV-KITCHEN-two-person-shift", "EV-RULES-house-friction",
    "EV-SIGNAL-first-anonymous-message", "EV-IDENTITY-profession-reveal",
    "EV-DATE-blind-box", "EV-DATE-mutual-signal",
    "EV-MISSED-empty-seat", "EV-CARE-breakfast-callback",
    "EV-TRIANGLE-reverse-invite", "EV-BRIDGE-hidden-courage",
    "EV-GROUP-truth-firepit", "EV-BOMBSHELL-ninth-card",
    "EV-PAST-consent-reveal", "EV-TRIP-last-two-days",
    "EV-FINAL-unsent-letter", "EV-FINAL-confession-day",
}
EVENT_ASSET_IDS = DAY1_ASSET_IDS | STORY_ASSET_IDS
GENDER_ZH = {"female": "女性", "male": "男性"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video = [item for item in streams if item.get("codec_type") == "video"]
    audio = [item for item in streams if item.get("codec_type") == "audio"]
    return {
        "duration": float((payload.get("format") or {}).get("duration") or 0),
        "video": video,
        "audio": audio,
    }


def decode(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decode", action="store_true", help="fully decode every promoted event and portrait")
    args = parser.parse_args()
    failures: list[str] = []
    runtime = load_json(RUNTIME_PATH)
    plan = load_json(PLAN_PATH)
    allowlist = load_json(ALLOWLIST_PATH)
    promotion = load_json(PROMOTION_PATH)
    cards_root = load_json(CARDS_PATH)
    cards = cards_root.get("characters") or cards_root.get("cards") or []

    items = [item for item in runtime.get("assets", []) if isinstance(item, dict)]
    ids = [str(item.get("id") or "") for item in items]
    duplicates = [asset_id for asset_id, count in Counter(ids).items() if asset_id and count > 1]
    if duplicates:
        failures.append(f"duplicate runtime IDs: {duplicates}")
    assets = {str(item.get("id")): item for item in items if item.get("id")}

    schemes = {
        str(item.get("id")): item for item in plan.get("schemes", [])
        if isinstance(item, dict) and item.get("id")
    }
    expected_schemes = {"F-A-jiangmi", "F-B-luyao", "M-A-chengye", "M-B-hechuan"}
    if set(schemes) != expected_schemes:
        failures.append(f"R6 scheme set mismatch: {sorted(schemes)}")
    expected_event_ids = {
        f"{base_id}--rotation-{scheme_id}"
        for base_id in EVENT_ASSET_IDS for scheme_id in expected_schemes
    }
    actual_event_ids = {
        asset_id for asset_id, asset in assets.items()
        if asset.get("kind") == "r6-gender-rotation-event"
    }
    if actual_event_ids != expected_event_ids:
        failures.append(
            f"event rotation inventory mismatch: missing={sorted(expected_event_ids - actual_event_ids)}, "
            f"extra={sorted(actual_event_ids - expected_event_ids)}"
        )

    card_ids = {
        str(card.get("id")) for card in cards
        if isinstance(card, dict) and card.get("id")
    }
    if len(card_ids) != 32:
        failures.append(f"expected expanded 32-card directory, found {len(card_ids)}")
    actual_portrait_ids = {
        asset_id for asset_id, asset in assets.items() if asset.get("kind") == "dynamic-portrait"
    }
    covered_card_ids = {
        asset_id.removeprefix("CHAR-").removesuffix("-portrait")
        for asset_id in actual_portrait_ids
        if asset_id.startswith("CHAR-") and asset_id.endswith("-portrait")
    }
    malformed_portrait_ids = sorted(
        asset_id for asset_id in actual_portrait_ids
        if not (asset_id.startswith("CHAR-") and asset_id.endswith("-portrait"))
    )
    if malformed_portrait_ids:
        failures.append(f"malformed dynamic portrait IDs: {malformed_portrait_ids}")
    if len(actual_portrait_ids) != 32 or len(covered_card_ids) != 32:
        failures.append(
            f"current identity-media coverage must contain 32 complete dynamic portraits, "
            f"got assets={len(actual_portrait_ids)} characters={len(covered_card_ids)}"
        )
    unknown_covered_ids = sorted(covered_card_ids - card_ids)
    if unknown_covered_ids:
        failures.append(f"dynamic portraits reference unknown character cards: {unknown_covered_ids}")
    planned_no_media_ids = card_ids - covered_card_ids

    allowlist_items = {
        str(item.get("sourceId")): item for item in allowlist.get("approvedAssets", [])
        if isinstance(item, dict) and item.get("sourceId")
    }
    promoted = [item for item in promotion.get("assets", []) if isinstance(item, dict)]
    if promotion.get("mode") != "applied" or len(promoted) != 108 or len(allowlist_items) != 108:
        failures.append(
            f"promotion/allowlist inventory must be applied 108/108, got "
            f"mode={promotion.get('mode')!r}, promotion={len(promoted)}, allowlist={len(allowlist_items)}"
        )

    promoted_runtime_ids: set[str] = set()
    source_types: Counter[str] = Counter()
    checked_paths: set[Path] = set()
    for row in promoted:
        manifest_asset = row.get("runtimeAsset") if isinstance(row.get("runtimeAsset"), dict) else {}
        asset_id = str(manifest_asset.get("id") or "")
        runtime_asset = assets.get(asset_id) or {}
        promoted_runtime_ids.add(asset_id)
        source_types[str(manifest_asset.get("sourceType") or "")] += 1
        derivative = runtime_asset.get("runtimeDerivative") if isinstance(runtime_asset.get("runtimeDerivative"), dict) else {}
        if derivative:
            if derivative.get("profile") != "render-mobile-lite-r10":
                failures.append(f"unexpected runtime derivative profile: {asset_id}")
                continue
            if derivative.get("sourceSha256") != manifest_asset.get("sha256"):
                failures.append(f"runtime derivative source SHA drifted from R6 promotion: {asset_id}")
                continue
            immutable_keys = {
                "id", "path", "kind", "status", "sourceId", "sourceType",
                "baseAssetId", "rotationSlot", "leadGender", "leadCharacterId",
                "identityCast", "identityScope", "qaVerdict", "visualQa", "visualQaEvidence",
            }
            drifted = sorted(
                key for key in immutable_keys
                if key in manifest_asset and runtime_asset.get(key) != manifest_asset.get(key)
            )
            if drifted:
                failures.append(f"runtime derivative metadata drifted for {asset_id}: {drifted}")
                continue
        elif runtime_asset != manifest_asset:
            failures.append(f"runtime manifest record drifted from applied promotion: {asset_id}")
            continue
        source_id = str(manifest_asset.get("sourceId") or "")
        approved = allowlist_items.get(source_id) or {}
        if approved.get("sha256") != manifest_asset.get("sha256"):
            failures.append(f"allowlist/runtime SHA mismatch: {asset_id}")

    if source_types != Counter({"generated": 81, "existing-runtime": 24, "local-composite": 3}):
        failures.append(f"promoted source type counts mismatch: {dict(source_types)}")
    expected_promoted_ids = expected_event_ids | {
        f"CHAR-{character_id}-portrait"
        for character_id in {"luyao", "yecheng", "tangli", "wenxu", "hechuan", "peiran", "lichuan", "qiaolan"}
    }
    if promoted_runtime_ids != expected_promoted_ids:
        failures.append("applied promotion does not map to the expected 100 events + 8 new portraits")

    expected_promoted_portrait_ids = promoted_runtime_ids - expected_event_ids
    for asset_id in sorted(expected_event_ids | expected_promoted_portrait_ids):
        asset = assets.get(asset_id)
        if not asset:
            continue
        raw_path = str(asset.get("path") or "")
        path = PUBLIC / raw_path.removeprefix("/")
        if not path.is_file():
            failures.append(f"missing runtime file: {asset_id} -> {raw_path}")
            continue
        digest = sha256_file(path)
        if digest != asset.get("sha256"):
            failures.append(f"runtime SHA mismatch: {asset_id}")
        try:
            media = probe(path)
            if args.decode and path not in checked_paths:
                decode(path)
                checked_paths.add(path)
        except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"media probe/decode failed for {asset_id}: {error}")
            continue
        if len(media["video"]) != 1 or media["video"][0].get("codec_name") != "h264":
            failures.append(f"{asset_id} must contain exactly one H.264 video stream")
        declared = asset.get("duration")
        if not isinstance(declared, (int, float)) or abs(float(declared) - media["duration"]) > 0.25:
            failures.append(f"duration mismatch: {asset_id}")
        if asset_id in expected_event_ids:
            base_id, scheme_id = asset_id.split("--rotation-", 1)
            scheme = schemes.get(scheme_id) or {}
            expected_gender = GENDER_ZH.get(str(scheme.get("gender") or ""))
            lead_id = str(scheme.get("leadId") or "")
            if asset.get("baseAssetId") != base_id or asset.get("rotationSlot") != scheme_id:
                failures.append(f"rotation route metadata mismatch: {asset_id}")
            if asset.get("leadGender") != expected_gender or asset.get("leadCharacterId") != lead_id:
                failures.append(f"rotation lead metadata mismatch: {asset_id}")
            identity_cast = asset.get("identityCast") if isinstance(asset.get("identityCast"), list) else []
            if lead_id not in identity_cast:
                failures.append(f"rotation lead missing from identityCast: {asset_id}")
            audio = asset.get("audio") if isinstance(asset.get("audio"), dict) else {}
            if len(media["audio"]) != 1 or media["audio"][0].get("codec_name") != "aac":
                failures.append(f"event rotation must contain one AAC stream: {asset_id}")
            if audio.get("hasAudio") is not True or audio.get("qaVerdict") != "passed":
                failures.append(f"event rotation audio manifest not passed: {asset_id}")
        elif media["audio"]:
            failures.append(f"dynamic portrait must be silent: {asset_id}")

    summary = {
        "verdict": "R6_RUNTIME_MEDIA_PASS" if not failures else "R6_RUNTIME_MEDIA_FAIL",
        "characterCards": len(card_ids),
        "mediaCoveredCharacters": len(covered_card_ids),
        "plannedNoMediaCharacters": len(planned_no_media_ids),
        "eventRotations": len(actual_event_ids),
        "dynamicPortraits": len(actual_portrait_ids),
        "promotedAssets": len(promoted),
        "fullyDecoded": len(checked_paths) if args.decode else 0,
        "runtimeManifestSha256": sha256_file(RUNTIME_PATH),
        "failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
