#!/usr/bin/env python3
"""Build the canonical, audit-friendly Heart Journey character asset registry.

This script does not rename or copy media.  It gives every existing runtime
asset a stable ASCII canonical identity while retaining its current public URL.
The Chinese display name is the human-review counterpart of that identity.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CARDS_PATH = ROOT / "content" / "character_cards.v3.json"
RUNTIME_MANIFEST_PATH = ROOT / "media" / "runtime-media-manifest.json"
R6_MANIFEST_PATH = ROOT / "media" / "production" / "gender-rotation-r6" / "manifest.r6.json"
OUTPUT_PATH = ROOT / "media" / "character-asset-registry.v1.json"


# Sequence codes are deliberately explicit.  Inserting a new story event must
# not silently renumber published asset identities.
EVENT_SPECS: dict[str, dict[str, str]] = {
    "D1-A1-island-hotel-establish": {
        "sequence": "101", "action": "arrive-island-hotel", "actionLabel": "抵达海岛酒店",
        "scene": "island-hotel-exterior", "sceneLabel": "海岛酒店外景",
    },
    "D1-A2-villa-entry": {
        "sequence": "102", "action": "enter-villa", "actionLabel": "走进心动小屋",
        "scene": "villa-foyer", "sceneLabel": "酒店玄关",
    },
    "D1-A3-cast-introductions": {
        "sequence": "103", "action": "cast-self-introduction", "actionLabel": "嘉宾自我介绍",
        "scene": "villa-living-room", "sceneLabel": "别墅客厅",
    },
    "D1-A3B-cast-first-impressions": {
        "sequence": "104", "action": "review-first-impressions", "actionLabel": "记录初见印象",
        "scene": "villa-living-room", "sceneLabel": "别墅客厅",
    },
    "D1-A4-icebreaker-selection": {
        "sequence": "105", "action": "choose-icebreaker-card", "actionLabel": "选择破冰任务",
        "scene": "villa-living-room", "sceneLabel": "别墅客厅",
    },
    "D1-A5-guided-smalltalk": {
        "sequence": "106", "action": "guided-smalltalk", "actionLabel": "第一次寒暄",
        "scene": "villa-common-area", "sceneLabel": "小屋公共区",
    },
    "D1-A6-first-dinner-team": {
        "sequence": "107", "action": "prepare-first-dinner", "actionLabel": "准备第一顿晚餐",
        "scene": "villa-kitchen", "sceneLabel": "小屋厨房",
    },
    "D1-A7-heart-message": {
        "sequence": "108", "action": "send-heart-message", "actionLabel": "发送心动短信",
        "scene": "guest-bedroom", "sceneLabel": "嘉宾卧室",
    },
    "D2-A1-memory-callback": {
        "sequence": "109", "action": "recall-first-day-memory", "actionLabel": "回想第一天记忆",
        "scene": "villa-breakfast-area", "sceneLabel": "小屋早餐区",
    },
    "EV-KITCHEN-two-person-shift": {
        "sequence": "201", "action": "two-person-kitchen-shift", "actionLabel": "双人厨房值班",
        "scene": "villa-kitchen", "sceneLabel": "小屋厨房",
    },
    "EV-RULES-house-friction": {
        "sequence": "202", "action": "resolve-house-rule-friction", "actionLabel": "处理生活规则摩擦",
        "scene": "villa-rule-board", "sceneLabel": "小屋值日板",
    },
    "EV-SIGNAL-first-anonymous-message": {
        "sequence": "203", "action": "read-first-anonymous-message", "actionLabel": "收发第一封匿名短信",
        "scene": "guest-bedroom", "sceneLabel": "嘉宾卧室",
    },
    "EV-IDENTITY-profession-reveal": {
        "sequence": "204", "action": "reveal-profession", "actionLabel": "公开职业身份",
        "scene": "villa-living-room", "sceneLabel": "别墅客厅",
    },
    "EV-DATE-blind-box": {
        "sequence": "205", "action": "open-date-blind-box", "actionLabel": "开启约会盲盒",
        "scene": "date-card-table", "sceneLabel": "约会卡桌",
    },
    "EV-DATE-mutual-signal": {
        "sequence": "206", "action": "follow-mutual-signal", "actionLabel": "回应双向信号",
        "scene": "seaside-date", "sceneLabel": "海边约会",
    },
    "EV-MISSED-empty-seat": {
        "sequence": "207", "action": "notice-empty-seat", "actionLabel": "发现被留空的座位",
        "scene": "villa-dining-area", "sceneLabel": "小屋餐区",
    },
    "EV-CARE-breakfast-callback": {
        "sequence": "208", "action": "prepare-breakfast-callback", "actionLabel": "准备匿名早餐",
        "scene": "villa-kitchen", "sceneLabel": "小屋厨房",
    },
    "EV-TRIANGLE-reverse-invite": {
        "sequence": "209", "action": "receive-reverse-invites", "actionLabel": "收到反向邀约",
        "scene": "villa-invite-board", "sceneLabel": "邀约卡墙",
    },
    "EV-BRIDGE-hidden-courage": {
        "sequence": "210", "action": "cross-water-bridge", "actionLabel": "挑战水上独木桥",
        "scene": "water-bridge", "sceneLabel": "水上独木桥",
    },
    "EV-GROUP-truth-firepit": {
        "sequence": "211", "action": "play-firepit-truth", "actionLabel": "围炉真心话",
        "scene": "beach-firepit", "sceneLabel": "海边篝火",
    },
    "EV-BOMBSHELL-ninth-card": {
        "sequence": "212", "action": "meet-bombshell-guest", "actionLabel": "迎接第九位嘉宾",
        "scene": "villa-entrance", "sceneLabel": "小屋入口",
    },
    "EV-PAST-consent-reveal": {
        "sequence": "213", "action": "choose-past-reveal", "actionLabel": "决定是否公开旧信",
        "scene": "private-letter-room", "sceneLabel": "私密信件室",
    },
    "EV-TRIP-last-two-days": {
        "sequence": "214", "action": "take-final-trip", "actionLabel": "开启告白前旅行",
        "scene": "island-road-trip", "sceneLabel": "海岛旅行",
    },
    "EV-FINAL-unsent-letter": {
        "sequence": "215", "action": "write-unsent-letter", "actionLabel": "写下未寄出的信",
        "scene": "confession-eve-bedroom", "sceneLabel": "告白前夜卧室",
    },
    "EV-FINAL-confession-day": {
        "sequence": "216", "action": "make-final-confession", "actionLabel": "最终告白",
        "scene": "seaside-confession-point", "sceneLabel": "海边告白点",
    },
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


def probe_media(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,sample_rate,channels",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    duration = float((payload.get("format") or {}).get("duration") or 0)
    return {
        "duration": round(duration, 6) if duration else None,
        "dimensions": {
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
        },
        "videoCodec": video.get("codec_name"),
        "audio": {
            "hasAudio": audio is not None,
            "codec": audio.get("codec_name") if audio else None,
            "sampleRate": int(audio.get("sample_rate") or 0) if audio else None,
            "channels": int(audio.get("channels") or 0) if audio else 0,
        },
    }


def character_directory(cards: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    directory: list[dict[str, Any]] = []
    for card in cards:
        character_id = str(card["id"])
        name = str((card.get("names") or {}).get("primary") or character_id)
        mbti = str(card.get("mbti") or "UNKNOWN").upper()
        gender = str((card.get("identity") or {}).get("gender") or "未知")
        card_id = f"character-card-{character_id}-{mbti.lower()}-v3"
        normalized = {
            "characterId": character_id,
            "characterName": name,
            "mbti": mbti,
            "gender": gender,
            "genderCode": "male" if gender == "男性" else "female" if gender == "女性" else "unknown",
            "characterCardId": card_id,
            "characterCardDisplayName": f"{name}-{mbti}-人物卡-v3",
            "characterCardPath": f"content/character_cards.v3.json#cards[id={character_id}]",
            "portraitRuntimePath": f"/media/portraits/{character_id}.jpg",
            "dynamicPortraitRuntimePath": f"/media/video/CHAR-{character_id}-portrait.mp4",
        }
        by_id[character_id] = normalized
        directory.append(normalized)
    return by_id, directory


def identity_fields(character: dict[str, Any] | None) -> dict[str, Any]:
    if character is None:
        return {
            "characterId": None, "characterName": "多角色", "mbti": "MULTI",
            "gender": "混合", "genderCode": "mixed", "characterCardRef": None,
        }
    return {
        "characterId": character["characterId"],
        "characterName": character["characterName"],
        "mbti": character["mbti"],
        "gender": character["gender"],
        "genderCode": character["genderCode"],
        "characterCardRef": character["characterCardId"],
    }


def make_name(
    character: dict[str, Any] | None,
    sequence: str,
    action: str,
    action_label: str,
    scene: str,
    scene_label: str,
    extension: str,
    variant: str | None = None,
    variant_label: str | None = None,
) -> tuple[str, str, str]:
    prefix = f"{character['characterId']}-{character['mbti'].lower()}" if character else "shared-multi"
    suffix = f"-{variant}" if variant else ""
    asset_id = f"hj-{prefix}-{sequence}-{action}-{scene}{suffix}"
    canonical_filename = f"{asset_id}.{extension.lower()}"
    name = character["characterName"] if character else "多角色"
    mbti = character["mbti"] if character else "MULTI"
    display_name = f"{name}-{mbti}-{sequence}-{action_label}-{scene_label}"
    if variant_label:
        display_name += f"-{variant_label}"
    return asset_id, canonical_filename, display_name


def rights_for(source_id: str | None, r6_shots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    shot = r6_shots.get(source_id or "")
    if not shot:
        return {
            "status": "unknown-not-reviewed",
            "likenessConsentRefIds": [],
            "voiceConsentRefIds": [],
            "claimBoundary": "No registry evidence currently proves commercial or public-release rights.",
        }
    return {
        "status": str(shot.get("rightsStatus") or "unknown-not-reviewed"),
        "likenessConsentRefIds": list(shot.get("likenessConsentRefIds") or []),
        "voiceConsentRefIds": list(shot.get("voiceConsentRefIds") or []),
        "claimBoundary": "R6 planning rights state is preserved; runtime approval is not a commercial-rights grant.",
    }


def main() -> int:
    cards_root = load_json(CARDS_PATH)
    runtime_root = load_json(RUNTIME_MANIFEST_PATH)
    r6_root = load_json(R6_MANIFEST_PATH)
    cards = [item for item in cards_root.get("cards", []) if isinstance(item, dict)]
    characters, directory = character_directory(cards)
    r6_shots = {
        str(item.get("id")): item for item in r6_root.get("shots", [])
        if isinstance(item, dict) and item.get("id")
    }
    assets: list[dict[str, Any]] = []

    # 16 static identity anchors are first-class review assets even though the
    # historical runtime manifest only indexed video.
    for character in directory:
        runtime_path = character["portraitRuntimePath"]
        source_path = f"frontend/public{runtime_path}"
        file_path = ROOT / source_path
        media = probe_media(file_path)
        asset_id, canonical, display = make_name(
            character, "000", "identity-anchor", "人物定妆照", "audit", "审核锚点", "jpg",
        )
        assets.append({
            "assetId": asset_id,
            "canonicalFilename": canonical,
            "displayName": display,
            **identity_fields(character),
            "sequence": "000",
            "sequenceNumber": 0,
            "action": "identity-anchor",
            "actionLabel": "人物定妆照",
            "scene": "audit",
            "sceneLabel": "审核锚点",
            "mediaType": "image",
            "usage": ["selection-card", "identity-reference", "character-review"],
            "identityCast": [character["characterId"]],
            "identityScope": "single",
            "sharedAsset": False,
            "sourcePath": source_path,
            "runtimePath": runtime_path,
            "legacyAssetId": None,
            "sha256": sha256_file(file_path),
            "duration": None,
            "dimensions": media["dimensions"],
            "audio": {"hasAudio": False, "mode": "not-applicable", "codec": None, "sampleRate": None, "channels": 0},
            "status": "approved-runtime",
            "rightsReview": "unknown-not-reviewed",
            "rights": rights_for(None, r6_shots),
            "source": {"type": "tracked-runtime-master", "manifestPath": None, "sourceId": None, "promptPath": None},
        })

    runtime_assets = [item for item in runtime_root.get("assets", []) if isinstance(item, dict)]
    for runtime in runtime_assets:
        legacy_id = str(runtime.get("id") or "")
        runtime_path = str(runtime.get("path") or "")
        source_path = f"frontend/public{runtime_path}"
        file_path = ROOT / source_path
        media = probe_media(file_path)
        extension = file_path.suffix.removeprefix(".")
        kind = str(runtime.get("kind") or "")
        source_id = str(runtime.get("sourceId") or "") or None
        identity_cast = [str(item) for item in runtime.get("identityCast", []) if item]
        lead_id = str(runtime.get("leadCharacterId") or "") or None
        character: dict[str, Any] | None = characters.get(lead_id or "")
        variant: str | None = None
        variant_label: str | None = None

        if kind == "dynamic-portrait":
            character_id = legacy_id.removeprefix("CHAR-").removesuffix("-portrait")
            character = characters[character_id]
            identity_cast = [character_id]
            sequence = "001"
            action, action_label = "first-appearance", "初次登场"
            scene, scene_label = "character-profile", "人物主页"
            usage = ["dynamic-portrait", "character-profile-background", "private-chat-background"]
            identity_scope = "single"
            shared_asset = False
        else:
            base_id = str(runtime.get("baseAssetId") or legacy_id.split("--rotation-", 1)[0].split("--", 1)[0])
            spec = EVENT_SPECS.get(base_id)
            if not spec:
                raise ValueError(f"Missing explicit event naming spec for {legacy_id} (base {base_id})")
            sequence = spec["sequence"]
            action, action_label = spec["action"], spec["actionLabel"]
            scene, scene_label = spec["scene"], spec["sceneLabel"]
            usage = ["event-background", "story-transition"]
            identity_scope = str(runtime.get("identityScope") or ("single" if len(identity_cast) == 1 else "group"))
            if kind == "r6-gender-rotation-event":
                slot = str(runtime.get("rotationSlot") or "unknown").lower()
                variant = f"r6-{slot}"
                variant_label = f"R6-{str(runtime.get('rotationSlot') or 'UNKNOWN')}"
                usage.append("perspective-route")
                shared_asset = False
            elif "--" in legacy_id:
                suffix = legacy_id.rsplit("--", 1)[1]
                suffix_character = characters.get(suffix)
                if suffix_character:
                    character = suffix_character
                    identity_cast = identity_cast or [suffix]
                variant = f"custom-{suffix.lower()}"
                variant_label = f"定制变体-{suffix}"
                shared_asset = character is None
            else:
                # Legacy pair/group masters have no explicit perspective lead.
                # Do not guess a protagonist from list order.
                if len(identity_cast) == 1:
                    character = characters.get(identity_cast[0])
                    shared_asset = False
                else:
                    character = None
                    shared_asset = True
                variant = "legacy-master"
                variant_label = "旧版母版"

        asset_id, canonical, display = make_name(
            character, sequence, action, action_label, scene, scene_label, extension,
            variant=variant, variant_label=variant_label,
        )
        manifest_audio = runtime.get("audio") if isinstance(runtime.get("audio"), dict) else {}
        rights = rights_for(source_id, r6_shots)
        audio_mode = manifest_audio.get("mode") or ("silent-loop" if not media["audio"]["hasAudio"] else "embedded")
        assets.append({
            "assetId": asset_id,
            "canonicalFilename": canonical,
            "displayName": display,
            **identity_fields(character),
            "sequence": sequence,
            "sequenceNumber": int(sequence),
            "action": action,
            "actionLabel": action_label,
            "scene": scene,
            "sceneLabel": scene_label,
            "mediaType": "video",
            "usage": usage,
            "identityCast": identity_cast,
            "identityScope": identity_scope,
            "sharedAsset": shared_asset,
            "sourcePath": source_path,
            "runtimePath": runtime_path,
            "legacyAssetId": legacy_id,
            "baseAssetId": runtime.get("baseAssetId") or (legacy_id.split("--rotation-", 1)[0] if kind == "r6-gender-rotation-event" else None),
            "rotationSlot": runtime.get("rotationSlot"),
            "sha256": str(runtime.get("sha256") or sha256_file(file_path)),
            "duration": media["duration"],
            "dimensions": media["dimensions"],
            "videoCodec": media["videoCodec"],
            "audio": {**media["audio"], "mode": audio_mode, "qaVerdict": manifest_audio.get("qaVerdict")},
            "status": str(runtime.get("status") or "approved-runtime"),
            "rightsReview": rights["status"],
            "rights": rights,
            "source": {
                "type": str(runtime.get("sourceType") or "tracked-runtime-master"),
                "manifestPath": "media/runtime-media-manifest.json",
                "sourceId": source_id,
                "promptPath": runtime.get("generationPromptFile"),
            },
        })

    counts = Counter(asset["mediaType"] for asset in assets)
    kind_counts = Counter(
        "static-portrait" if asset["mediaType"] == "image"
        else "dynamic-portrait" if asset["sequence"] == "001"
        else "event-route"
        for asset in assets
    )
    registry = {
        "schemaVersion": "heart-journey/character-asset-registry-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "audit-registry-active",
        "namingContract": {
            "assetId": "hj-{characterId|shared}-{mbti|multi}-{sequence}-{action}-{scene}[-variant]",
            "canonicalFilename": "{assetId}.{extension}",
            "displayName": "{中文名}-{MBTI}-{sequence}-{中文动作}-{中文场景}[-变体]",
            "physicalRenamePolicy": "registry-alias-only; current runtime files are not copied or renamed",
        },
        "sourceManifests": {
            "characterCards": {"path": "content/character_cards.v3.json", "sha256": sha256_file(CARDS_PATH)},
            "runtimeMedia": {"path": "media/runtime-media-manifest.json", "sha256": sha256_file(RUNTIME_MANIFEST_PATH)},
            "r6Plan": {"path": "media/production/gender-rotation-r6/manifest.r6.json", "sha256": sha256_file(R6_MANIFEST_PATH)},
        },
        "summary": {
            "characters": len(directory),
            "assets": len(assets),
            "images": counts["image"],
            "videos": counts["video"],
            "staticPortraits": kind_counts["static-portrait"],
            "dynamicPortraits": kind_counts["dynamic-portrait"],
            "eventRoutes": kind_counts["event-route"],
        },
        "characters": directory,
        "assets": assets,
    }
    OUTPUT_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(registry["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
