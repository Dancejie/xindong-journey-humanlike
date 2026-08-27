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

    cards_root = load_json(root / "content" / "character_cards.v3.json")
    runtime_root = load_json(root / "media" / "runtime-media-manifest.json")
    cards = [item for item in cards_root.get("cards", []) if isinstance(item, dict)]
    card_by_id = {str(item.get("id")): item for item in cards if item.get("id")}
    runtime_assets = [item for item in runtime_root.get("assets", []) if isinstance(item, dict)]
    runtime_by_id = {str(item.get("id")): item for item in runtime_assets if item.get("id")}
    directory = [item for item in registry.get("characters", []) if isinstance(item, dict)]
    assets = [item for item in registry.get("assets", []) if isinstance(item, dict)]

    if len(card_by_id) != 16 or len(directory) != 16:
        failures.append(f"expected 16 character cards and directory rows, got cards={len(card_by_id)} directory={len(directory)}")
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
    if (len(static_portraits), len(dynamic_portraits), len(event_routes)) != (16, 16, len(runtime_assets) - 16):
        failures.append(
            f"inventory counts mismatch: static={len(static_portraits)} dynamic={len(dynamic_portraits)} "
            f"eventRoutes={len(event_routes)} expectedEvents={len(runtime_assets) - 16}"
        )

    # Every playable identity must have exactly one static and one dynamic
    # portrait, both bound to that same identity.
    for character_id in sorted(card_by_id):
        static = [item for item in static_portraits if item.get("characterId") == character_id]
        dynamic = [item for item in dynamic_portraits if item.get("characterId") == character_id]
        if len(static) != 1 or len(dynamic) != 1:
            failures.append(f"portrait coverage mismatch for {character_id}: static={len(static)} dynamic={len(dynamic)}")

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
