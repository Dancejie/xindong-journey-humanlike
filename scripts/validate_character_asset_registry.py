#!/usr/bin/env python3
"""Validate the canonical Heart Journey character/media registry."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "media" / "character-asset-registry.v1.json"
CARDS_PATH = ROOT / "content" / "character_cards.v3.json"
RUNTIME_PATH = ROOT / "media" / "runtime-media-manifest.json"
ASSET_ID_RE = re.compile(
    r"^hj-(?:[a-z0-9]+-[a-z0-9]+|shared-multi)-[0-9]{3}-[a-z0-9-]+$"
)
SOURCE_MANIFEST_PATHS = {
    "characterCards": "content/character_cards.v3.json",
    "runtimeMedia": "media/runtime-media-manifest.json",
    "r6Plan": "media/production/gender-rotation-r6/manifest.r6.json",
}
MBTI_TYPES = {
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
}


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


def validate_registry(
    registry: dict[str, Any],
    *,
    root: Path = ROOT,
    verify_hashes: bool = True,
) -> list[str]:
    failures: list[str] = []
    if registry.get("schemaVersion") != "heart-journey/character-asset-registry-v1":
        failures.append("unexpected registry schemaVersion")

    source_manifests = registry.get("sourceManifests")
    if not isinstance(source_manifests, dict):
        failures.append("sourceManifests must be an object")
        source_manifests = {}
    for source_id, expected_path in SOURCE_MANIFEST_PATHS.items():
        source = source_manifests.get(source_id)
        if not isinstance(source, dict):
            failures.append(f"missing source manifest binding: {source_id}")
            continue
        if source.get("path") != expected_path:
            failures.append(
                f"source manifest path mismatch: {source_id} expected={expected_path!r} actual={source.get('path')!r}"
            )
            continue
        declared_sha = str(source.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", declared_sha):
            failures.append(f"invalid source manifest SHA-256: {source_id}")
            continue
        source_path = root / expected_path
        if not source_path.is_file():
            failures.append(f"missing bound source manifest: {source_id} -> {expected_path}")
        elif verify_hashes:
            actual_sha = sha256_file(source_path)
            if actual_sha != declared_sha:
                failures.append(
                    f"source manifest SHA mismatch: {source_id} declared={declared_sha} actual={actual_sha}"
                )

    cards_root = load_json(root / "content" / "character_cards.v3.json")
    runtime_root = load_json(root / "media" / "runtime-media-manifest.json")
    cards = [item for item in cards_root.get("cards", []) if isinstance(item, dict)]
    card_by_id = {str(item.get("id")): item for item in cards if item.get("id")}
    runtime_assets = [item for item in runtime_root.get("assets", []) if isinstance(item, dict)]
    runtime_by_id = {str(item.get("id")): item for item in runtime_assets if item.get("id")}
    directory = [item for item in registry.get("characters", []) if isinstance(item, dict)]
    assets = [item for item in registry.get("assets", []) if isinstance(item, dict)]

    if len(card_by_id) != 32 or len(directory) != 32:
        failures.append(f"expected 32 character cards and directory rows, got cards={len(card_by_id)} directory={len(directory)}")
    roster_pairs = Counter(
        (
            str(card.get("mbti") or "").upper(),
            str((card.get("identity") or {}).get("gender") or ""),
        )
        for card in card_by_id.values()
    )
    expected_pairs = {
        (mbti, gender): 1
        for mbti in MBTI_TYPES
        for gender in ("男性", "女性")
    }
    if dict(roster_pairs) != expected_pairs:
        failures.append("full MBTI roster must contain exactly one male and one female card per type")
    directory_by_id = {str(item.get("characterId")): item for item in directory if item.get("characterId")}
    if set(directory_by_id) != set(card_by_id):
        failures.append("character directory IDs do not exactly match v3 character cards")
    for character_id, card in card_by_id.items():
        row = directory_by_id.get(character_id) or {}
        expected_name = str((card.get("names") or {}).get("primary") or "")
        expected_mbti = str(card.get("mbti") or "").upper()
        expected_gender = str((card.get("identity") or {}).get("gender") or "")
        if row.get("characterName") != expected_name or row.get("mbti") != expected_mbti or row.get("gender") != expected_gender:
            failures.append(f"character directory metadata mismatch: {character_id}")
        expected_card_id = f"character-card-{character_id}-{expected_mbti.lower()}-v3"
        if row.get("characterCardId") != expected_card_id:
            failures.append(f"character card canonical ID mismatch: {character_id}")

    ids = [str(item.get("assetId") or "") for item in assets]
    filenames = [str(item.get("canonicalFilename") or "") for item in assets]
    legacy_ids = [str(item.get("legacyAssetId")) for item in assets if item.get("legacyAssetId")]
    for label, values in (("assetId", ids), ("canonicalFilename", filenames), ("legacyAssetId", legacy_ids)):
        duplicates = sorted(value for value, count in Counter(values).items() if value and count > 1)
        if duplicates:
            failures.append(f"duplicate {label}: {duplicates}")
    if set(legacy_ids) != set(runtime_by_id):
        failures.append(
            "runtime inventory mismatch: "
            f"missing={sorted(set(runtime_by_id) - set(legacy_ids))} "
            f"extra={sorted(set(legacy_ids) - set(runtime_by_id))}"
        )

    static_portraits = [item for item in assets if item.get("mediaType") == "image" and item.get("sequence") == "000"]
    dynamic_portraits = [item for item in assets if item.get("mediaType") == "video" and item.get("sequence") == "001"]
    event_routes = [item for item in assets if item.get("mediaType") == "video" and item.get("sequence") not in {"001"}]
    if len(event_routes) != len(runtime_assets) - len(dynamic_portraits):
        failures.append(
            f"inventory counts mismatch: static={len(static_portraits)} dynamic={len(dynamic_portraits)} "
            f"eventRoutes={len(event_routes)} expectedEvents={len(runtime_assets) - len(dynamic_portraits)}"
        )

    # A character is fully identity-covered, explicitly static-only because a
    # generated moving portrait was held, or explicitly planned with no media.
    # Unexplained partial coverage is never accepted.
    media_covered_ids: set[str] = set()
    static_only_held_ids: set[str] = set()
    planned_no_media_ids: set[str] = set()
    for character_id in sorted(card_by_id):
        static = [item for item in static_portraits if item.get("characterId") == character_id]
        dynamic = [item for item in dynamic_portraits if item.get("characterId") == character_id]
        card = card_by_id[character_id]
        row = directory_by_id.get(character_id) or {}
        coverage = row.get("mediaCoverage") if isinstance(row.get("mediaCoverage"), dict) else {}
        if len(static) == 1 and len(dynamic) == 1:
            media_covered_ids.add(character_id)
            expected_coverage_status = "runtime-identity-covered"
        elif len(static) == 1 and len(dynamic) == 0:
            static_only_held_ids.add(character_id)
            expected_coverage_status = "runtime-static-only-held-dynamic"
            media = card.get("media") if isinstance(card.get("media"), dict) else {}
            if (
                media.get("status") != "planned"
                or media.get("generationRequired") is not True
                or media.get("runtimeStatus") != "blocked"
                or str(card.get("video") or "").strip()
            ):
                failures.append(f"static-only card is not explicitly held/blocked: {character_id}")
        elif len(static) == 0 and len(dynamic) == 0:
            planned_no_media_ids.add(character_id)
            expected_coverage_status = "planned-no-runtime-identity-media"
            media = card.get("media") if isinstance(card.get("media"), dict) else {}
            if (
                media.get("status") != "planned"
                or media.get("generationRequired") is not True
                or media.get("runtimeStatus") != "blocked"
                or str(card.get("video") or "").strip()
            ):
                failures.append(f"missing-media card is not explicitly planned/blocked: {character_id}")
        else:
            failures.append(f"portrait coverage mismatch for {character_id}: static={len(static)} dynamic={len(dynamic)}")
            expected_coverage_status = "partial-invalid"
        if coverage != {
            "status": expected_coverage_status,
            "staticPortraitAssetCount": len(static),
            "dynamicPortraitAssetCount": len(dynamic),
        }:
            failures.append(f"character mediaCoverage drift: {character_id}")

    hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for asset in assets:
        asset_id = str(asset.get("assetId") or "")
        canonical = str(asset.get("canonicalFilename") or "")
        media_type = str(asset.get("mediaType") or "")
        source_path = str(asset.get("sourcePath") or "")
        runtime_path = str(asset.get("runtimePath") or "")
        character_id = asset.get("characterId")
        identity_cast = asset.get("identityCast") if isinstance(asset.get("identityCast"), list) else []
        identity_scope = str(asset.get("identityScope") or "")
        sha = str(asset.get("sha256") or "")
        dimensions = asset.get("dimensions") if isinstance(asset.get("dimensions"), dict) else {}
        audio = asset.get("audio") if isinstance(asset.get("audio"), dict) else {}

        if not ASSET_ID_RE.fullmatch(asset_id):
            failures.append(f"invalid canonical assetId: {asset_id}")
        suffix = ".jpg" if media_type == "image" else ".mp4" if media_type == "video" else ""
        if canonical != f"{asset_id}{suffix}":
            failures.append(f"canonical filename/extension mismatch: {asset_id}")
        if not re.fullmatch(r"[0-9]{3}", str(asset.get("sequence") or "")):
            failures.append(f"invalid sequence code: {asset_id}")
        for field in ("action", "actionLabel", "scene", "sceneLabel", "displayName", "status", "rightsReview"):
            if not asset.get(field):
                failures.append(f"missing {field}: {asset_id}")

        if not runtime_path.startswith("/media/") or source_path != f"frontend/public{runtime_path}":
            failures.append(f"source/runtime path contract mismatch: {asset_id}")
        runtime_references = asset.get("runtimeReferences")
        if runtime_references is not None:
            if not isinstance(runtime_references, list) or not runtime_references:
                failures.append(f"runtimeReferences must be a non-empty array: {asset_id}")
            else:
                for index, reference in enumerate(runtime_references):
                    if not isinstance(reference, dict):
                        failures.append(f"invalid runtime reference row {index}: {asset_id}")
                        continue
                    reference_path = reference.get("path")
                    reference_line = reference.get("lineHint")
                    reference_match = reference.get("match")
                    if not isinstance(reference_path, str) or not reference_path or Path(reference_path).is_absolute():
                        failures.append(f"invalid runtime reference path {index}: {asset_id}")
                        continue
                    if isinstance(reference_line, bool) or not isinstance(reference_line, int) or reference_line < 1:
                        failures.append(f"invalid runtime reference lineHint {index}: {asset_id}")
                        continue
                    if reference_match != runtime_path:
                        failures.append(f"runtime reference match/path mismatch {index}: {asset_id}")
                        continue
                    evidence_path = root / reference_path
                    if not evidence_path.is_file():
                        failures.append(f"missing runtime reference evidence {index}: {asset_id} -> {reference_path}")
                        continue
                    evidence_text = evidence_path.read_text(encoding="utf-8")
                    if runtime_path not in evidence_text:
                        failures.append(
                            f"runtime reference evidence drift {index}: {asset_id} -> {reference_path}"
                        )
        file_path = root / source_path
        if not file_path.is_file():
            failures.append(f"missing source media: {asset_id} -> {source_path}")
        elif verify_hashes and sha256_file(file_path) != sha:
            failures.append(f"SHA mismatch: {asset_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            failures.append(f"invalid SHA-256: {asset_id}")
        else:
            hash_groups[sha].append(asset)
        if int(dimensions.get("width") or 0) <= 0 or int(dimensions.get("height") or 0) <= 0:
            failures.append(f"invalid dimensions: {asset_id}")
        if not isinstance(audio.get("hasAudio"), bool):
            failures.append(f"audio.hasAudio must be boolean: {asset_id}")
        if media_type == "video" and not isinstance(asset.get("duration"), (int, float)):
            failures.append(f"video duration missing: {asset_id}")
        if media_type == "image" and asset.get("duration") is not None:
            failures.append(f"image duration must be null: {asset_id}")

        unknown_cast = sorted(set(identity_cast) - set(card_by_id))
        if unknown_cast:
            failures.append(f"unknown identityCast IDs in {asset_id}: {unknown_cast}")
        if identity_scope == "single":
            if len(identity_cast) != 1 or character_id != identity_cast[0]:
                failures.append(f"single-identity scope mismatch: {asset_id}")
            if asset.get("sharedAsset") is not False:
                failures.append(f"single-identity asset cannot be shared: {asset_id}")
        if character_id:
            card = card_by_id.get(str(character_id))
            if not card:
                failures.append(f"unknown primary characterId: {asset_id}")
            else:
                expected_name = (card.get("names") or {}).get("primary")
                expected_mbti = str(card.get("mbti") or "").upper()
                expected_gender = (card.get("identity") or {}).get("gender")
                if (asset.get("characterName"), asset.get("mbti"), asset.get("gender")) != (expected_name, expected_mbti, expected_gender):
                    failures.append(f"primary character metadata mismatch: {asset_id}")
                if asset.get("characterCardRef") != f"character-card-{character_id}-{expected_mbti.lower()}-v3":
                    failures.append(f"character card reference mismatch: {asset_id}")
                if character_id not in identity_cast:
                    failures.append(f"primary character absent from identityCast: {asset_id}")
        elif asset.get("sharedAsset") is not True:
            failures.append(f"asset without a primary character must be explicitly shared: {asset_id}")

        legacy_id = asset.get("legacyAssetId")
        if legacy_id:
            runtime = runtime_by_id.get(str(legacy_id)) or {}
            if runtime.get("path") != runtime_path or runtime.get("sha256") != sha:
                failures.append(f"runtime manifest binding drift: {asset_id}")
            lead = runtime.get("leadCharacterId")
            if lead and (character_id != lead or lead not in identity_cast):
                failures.append(f"runtime lead/registry identity mismatch: {asset_id}")

    # Reuse is safe only when the same bytes declare the same people.  A hash
    # shared by different identity sets is a potential character substitution,
    # even if both files have plausible names.
    for sha, group in hash_groups.items():
        cast_signatures = {tuple(sorted(str(item) for item in asset.get("identityCast", []))) for asset in group}
        if len(cast_signatures) > 1:
            failures.append(
                f"cross-identity SHA reuse without one identity contract: {sha} -> "
                f"{[asset.get('assetId') for asset in group]}"
            )

    summary = registry.get("summary") if isinstance(registry.get("summary"), dict) else {}
    expected_summary = {
        "characters": len(directory), "assets": len(assets),
        "mediaCoveredCharacters": len(media_covered_ids),
        "staticOnlyHeldCharacters": len(static_only_held_ids),
        "plannedNoMediaCharacters": len(planned_no_media_ids),
        "images": len([item for item in assets if item.get("mediaType") == "image"]),
        "videos": len([item for item in assets if item.get("mediaType") == "video"]),
        "staticPortraits": len(static_portraits), "dynamicPortraits": len(dynamic_portraits),
        "eventRoutes": len(event_routes),
    }
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        failures.append(f"registry summary drift: expected={expected_summary}, actual={summary}")
    return failures


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    failures = validate_registry(registry)
    summary = registry.get("summary") if isinstance(registry.get("summary"), dict) else {}
    result = {
        "verdict": "CHARACTER_ASSET_REGISTRY_PASS" if not failures else "CHARACTER_ASSET_REGISTRY_FAIL",
        **summary,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
