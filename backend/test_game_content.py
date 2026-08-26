import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.game_content import (
    CHARACTER_CARDS,
    CHARACTER_CARD_MAP,
    CARD_PACKAGE,
    CHARACTER_MAP,
    CONTENT_VERSION,
    DAY1_MEDIA_CONTRACT,
    LEGACY_CAST_IDS,
    NODES,
    RELATIONSHIP_AXES,
    _public_character,
    active_cast_ids,
    available_chat_contexts,
    apply_choice,
    build_fallback_script_flavor,
    commit_agent_turn,
    create_snapshot as _create_snapshot,
    detect_repetitive_agent_reply,
    heart_message_suggestions,
    media_rotation_for,
    migrate_snapshot,
    normalize_conversation_context,
    project_view,
    resolve_identity_safe_media,
    select_run_cast,
    validate_agent_turn,
)
from backend.agent_prompt import (
    build_agent_messages,
    build_chat_opening_messages,
    extract_json,
    fallback_chat_opening,
    runtime_character_card,
    select_runtime_few_shots,
    validate_chat_opening,
)
from backend.day1_script import (
    build_day1_node_messages,
    install_cached_day1_script,
    install_day1_node_script,
    install_day1_script,
    validate_day1_node_script,
    validate_day1_script,
)


def valid_turn(card):
    fallback_background = {
        "shenmo": "我在投行工作", "linyu": "我是建筑工程师", "chengye": "我在经营极限运动品牌",
        "guyan": "我做游戏策划", "jiangwan": "我是心理咨询师", "jiangmi": "我喜欢录声音日记",
        "sunnian": "我是插画师", "chensu": "我平时喜欢修旧相机",
    }
    occupation = card.get("sourceProfile", {}).get("facts", {}).get("occupation")
    background = fallback_background.get(card["id"], f"我是{occupation}")
    return {
        "dialogue": f"你好，我是{card['names']['primary']}，MBTI是{card['mbti']}，{background}。这次来这里，是想从一件具体的小事开始认识一个人。你呢？",
        "stageDirection": "对方把身体转向你，认真等你回答",
        "attitude": "curious",
        "intentId": card["agentPolicy"]["allowedIntentIds"][0],
        "publicReason": "具体表达让关系判断发生变化",
        "relationshipDelta": {axis: 3 for axis in RELATIONSHIP_AXES},
        "memory": {"kind": "episodic", "summary": "玩家作出一次具体表达", "interpretation": "对方愿意承担下一步", "salience": 70, "emotionalValence": 25},
        "proposedEventId": card["eventPolicy"]["eventId"],
    }


def create_snapshot(user_mbti="INFP", perspective_character_id=None):
    """Legacy-focused fixture; production ``_create_snapshot`` still seeds a new 8-person cast."""
    snapshot = _create_snapshot(user_mbti, perspective_character_id)
    perspective_id = snapshot["player"]["perspectiveCharacterId"]
    if perspective_id in LEGACY_CAST_IDS:
        snapshot["castIds"] = list(LEGACY_CAST_IDS)
        snapshot = migrate_snapshot(snapshot)
        snapshot["scriptFlavor"] = build_fallback_script_flavor(perspective_id, list(LEGACY_CAST_IDS))
    return snapshot


def snapshot_with_character(character_id: str):
    card = CHARACTER_CARD_MAP[character_id]
    counterpart = next(item for item in CHARACTER_CARDS if item["mbti"] == card["mbti"] and item["id"] != character_id)
    snapshot = _create_snapshot(counterpart["mbti"], counterpart["id"])
    assert character_id in active_cast_ids(snapshot)
    return snapshot


class CharacterCardContractTests(unittest.TestCase):
    def test_dual_roster_all_protagonists_keep_seeded_balanced_eight_person_cast(self):
        for card in CHARACTER_CARDS:
            for seed in ("seed-a", "seed-b", "seed-c", "seed-d"):
                cast_ids = select_run_cast(card["id"], seed)
                self.assertEqual(cast_ids, select_run_cast(card["id"], seed))
                self.assertEqual(8, len(cast_ids))
                self.assertEqual(8, len(set(cast_ids)))
                self.assertIn(card["id"], cast_ids)
                genders = [CHARACTER_MAP[character_id]["gender"] for character_id in cast_ids]
                self.assertEqual(4, genders.count("男性"))
                self.assertEqual(4, genders.count("女性"))
                counterpart_ids = [
                    character_id for character_id in cast_ids
                    if character_id != card["id"] and CHARACTER_MAP[character_id]["mbti"] == card["mbti"]
                ]
                self.assertEqual(1, len(counterpart_ids))
                self.assertNotEqual(CHARACTER_MAP[card["id"]]["gender"], CHARACTER_MAP[counterpart_ids[0]]["gender"])

    def test_runtime_few_shot_retrieval_uses_observable_message_and_scene_cues(self):
        card = json.loads(json.dumps(CHARACTER_CARD_MAP["chensu"], ensure_ascii=False))
        card["fewShots"] = [
            {"id": "fs.chensu.opening", "context": "初次见面", "player": "你好", "attitude": "curious", "reply": "先从眼前的小事聊。"},
            {"id": "fs.chensu.support", "context": "被具体支持", "player": "我可以帮你", "attitude": "warm", "reply": "那一起做，但不用全替我做。"},
            {"id": "fs.chensu.challenge", "context": "判断受到质疑", "player": "我不信", "attitude": "challenging", "reply": "先试一次，再看结果。"},
            {"id": "fs.chensu.boundary", "context": "边界被逼迫", "player": "你必须现在答应", "attitude": "boundary", "reply": "别替我决定。"},
        ]
        selected = select_runtime_few_shots(
            card, "我不喜欢被逼，你不要替我决定",
            {"nodeId": "guided-chat", "conversationMode": "reopening", "currentAttitude": "boundary"},
        )
        self.assertEqual("chensu", selected["characterId"])
        self.assertEqual("fs.chensu.boundary", selected["items"][0]["id"])
        self.assertIn("boundary", selected["selectionBasis"]["observableCues"])
        self.assertEqual(3, len(selected["items"]))
        self.assertTrue(all("chosenTactic" in item and "repairOrExit" in item for item in selected["items"]))

    def test_runtime_character_card_strips_source_lines_and_unselected_examples(self):
        card = CHARACTER_CARD_MAP["shenmo"]
        projected = runtime_character_card(card)
        serialized = json.dumps(projected, ensure_ascii=False)
        self.assertNotIn("fewShots", projected)
        self.assertNotIn("sourceRefIds", projected)
        self.assertNotIn("microExcerpt", serialized)
        self.assertEqual(
            {"facts", "adaptationBoundary"},
            set(projected.get("sourceProfile", {})),
        )
        self.assertTrue(all(
            set(anchor).issubset({"observablePattern", "transferRule"})
            for anchor in projected.get("researchAnchors", [])
        ))
        source_line = card["researchAnchors"][0].get("microExcerpt")
        if source_line:
            self.assertNotIn(source_line, serialized)
        self.assertIn(card["researchAnchors"][0]["observablePattern"], serialized)

    def test_all_runtime_prompts_strip_authoring_provenance_but_keep_behavior_transfer(self):
        forbidden_field_names = (
            '"sourceRefIds"', '"sourceRefId"', '"sourceEvidenceIds"',
            '"sourceName"', '"sourceMbti"', '"alignment"',
            '"work"', '"locator"', '"microExcerpt"',
        )
        for card in CHARACTER_CARDS:
            with self.subTest(character=card["id"]):
                target_snapshot = snapshot_with_character(card["id"])
                player_card = CHARACTER_CARD_MAP[target_snapshot["player"]["perspectiveCharacterId"]]
                protagonist_snapshot = _create_snapshot(card["mbti"], card["id"])
                prompt_copies = {
                    "runtimeCard": json.dumps(runtime_character_card(card), ensure_ascii=False),
                    "agent": "\n".join(
                        item["content"] for item in build_agent_messages(
                            card, target_snapshot, "我愿意听你把这件事说清楚。", player_card,
                        )
                    ),
                    "opening": "\n".join(
                        item["content"] for item in build_chat_opening_messages(
                            card, target_snapshot, player_card,
                        )
                    ),
                    "day1": "\n".join(
                        item["content"] for item in build_day1_node_messages(
                            protagonist_snapshot, "team-up",
                        )
                    ),
                }
                source_markers = set(card.get("sourceRefIds") or [])
                for anchor in card.get("researchAnchors") or []:
                    source_markers.update(
                        str(anchor.get(key))
                        for key in ("sourceRefId", "work", "locator")
                        if anchor.get(key)
                    )
                for shot in card.get("fewShots") or []:
                    source_markers.update(str(item) for item in shot.get("sourceEvidenceIds") or [])
                for prompt_kind, serialized in prompt_copies.items():
                    for field_name in forbidden_field_names:
                        self.assertNotIn(field_name, serialized, f"{card['id']} {prompt_kind}")
                    for marker in source_markers:
                        self.assertNotIn(marker, serialized, f"{card['id']} {prompt_kind}: {marker}")
                self.assertIn(
                    card["researchAnchors"][0]["observablePattern"],
                    prompt_copies["runtimeCard"],
                )

    def test_media_rotation_is_stable_and_never_crosses_player_gender(self):
        for card in CHARACTER_CARDS:
            rotation = media_rotation_for(card["id"], "stable-run")
            self.assertEqual(rotation, media_rotation_for(card["id"], "stable-run"))
            self.assertEqual(CHARACTER_MAP[card["id"]]["gender"], rotation["leadGender"])
            self.assertIn(card["mbti"], rotation["selectionBucket"])
            expected_prefix = "M-" if rotation["leadGender"] == "男性" else "F-"
            self.assertTrue(rotation["slot"].startswith(expected_prefix))
            self.assertEqual(rotation["leadGender"], CHARACTER_MAP[rotation["anchorCharacterId"]]["gender"])

    def test_media_rotation_is_event_specific_and_independent_of_run_id(self):
        event_asset_ids = [contract["assetId"] for contract in DAY1_MEDIA_CONTRACT.values()]
        for card in CHARACTER_CARDS:
            rotations_a = [media_rotation_for(card["id"], "run-a", event_id) for event_id in event_asset_ids]
            rotations_b = [media_rotation_for(card["id"], "run-b", event_id) for event_id in event_asset_ids]
            self.assertEqual(rotations_a, rotations_b)
            self.assertEqual(2, len({rotation["slot"] for rotation in rotations_a}))
            self.assertTrue(all(rotation["leadGender"] == CHARACTER_MAP[card["id"]]["gender"] for rotation in rotations_a))
            self.assertTrue(all(rotation["eventId"] in event_asset_ids for rotation in rotations_a))

    def test_production_english_gender_is_normalized_at_runtime(self):
        assets = {
            "D1-A2-villa-entry--rotation-F-A-jiangmi": {
                "path": "/media/video/female-scheme.mp4", "status": "approved-runtime", "leadGender": "female",
            },
        }
        media = resolve_identity_safe_media(
            "D1-A2-villa-entry", "jiangmi", [], current_cast_ids=list(LEGACY_CAST_IDS),
            rotation={"slot": "F-A-jiangmi", "leadGender": "female", "anchorCharacterId": "jiangmi"},
            asset_map=assets,
        )
        self.assertEqual("D1-A2-villa-entry--rotation-F-A-jiangmi", media["assetId"])
        self.assertEqual("女性", media["leadGender"])
        self.assertEqual("approved-gender-rotation", media["selectionReason"])

    def test_rotation_uses_an_in_cast_same_gender_anchor_instead_of_a_stranger(self):
        assets = {
            "D1-A3-cast-introductions--rotation-M-A-chengye": {
                "path": "/media/video/chengye.mp4", "status": "approved-runtime", "leadGender": "男性",
                "identityCast": ["chengye"],
            },
            "D1-A3-cast-introductions--rotation-M-B-hechuan": {
                "path": "/media/video/hechuan.mp4", "status": "approved-runtime", "leadGender": "男性",
                "identityCast": ["hechuan"],
            },
        }
        cast_ids = ["peiran", "jiangmi", "hechuan", "linyu", "sunnian", "guyan", "chensu", "jiangwan"]
        media = resolve_identity_safe_media(
            "D1-A3-cast-introductions", "peiran", [], current_cast_ids=cast_ids,
            rotation={"slot": "M-A-chengye", "leadGender": "男性", "anchorCharacterId": "chengye", "eventId": "D1-A3-cast-introductions"},
            asset_map=assets,
        )
        self.assertEqual("D1-A3-cast-introductions--rotation-M-B-hechuan", media["assetId"])
        self.assertEqual("M-B-hechuan", media["rotationSlot"])
        self.assertEqual(["hechuan"], media["identityCast"])
        self.assertTrue(set(media["identityCast"]).issubset(cast_ids))

    def test_rotation_with_any_out_of_cast_visible_person_falls_back_to_player(self):
        assets = {
            "D1-A3B-cast-first-impressions--rotation-M-B-hechuan": {
                "path": "/media/video/hechuan-and-outsider.mp4", "status": "approved-runtime", "leadGender": "男性",
                "identityCast": ["hechuan", "jiangwan"], "duration": 8,
            },
            "CHAR-peiran-portrait": {
                "path": "/media/video/CHAR-peiran-portrait.mp4", "status": "approved-runtime", "identityCast": ["peiran"],
            },
        }
        cast_ids = ["peiran", "jiangmi", "hechuan", "linyu", "sunnian", "guyan", "chensu", "luyao"]
        media = resolve_identity_safe_media(
            "D1-A3B-cast-first-impressions", "peiran", [], routing_mode="current-eight", current_cast_ids=cast_ids,
            rotation={"slot": "M-B-hechuan", "leadGender": "男性", "anchorCharacterId": "hechuan"},
            asset_map=assets,
        )
        self.assertEqual("CHAR-peiran-portrait", media["assetId"])
        self.assertEqual(["peiran"], media["identityCast"])
        self.assertEqual("/media/video/CHAR-peiran-portrait.mp4", media["src"])

    def test_reviewed_composite_gets_edit_aligned_three_second_identity_plates(self):
        assets = {
            "D1-A3B-cast-first-impressions--rotation-M-B-hechuan": {
                "path": "/media/video/hechuan-jiangwan.mp4", "status": "approved-runtime", "leadGender": "男性",
                "identityCast": ["hechuan", "jiangwan"], "duration": 8, "sourceType": "local-composite",
            },
        }
        cast_ids = ["hechuan", "jiangwan", "jiangmi", "linyu", "sunnian", "guyan", "chensu", "luyao"]
        media = resolve_identity_safe_media(
            "D1-A3B-cast-first-impressions", "hechuan", [], routing_mode="current-eight", current_cast_ids=cast_ids,
            rotation={"slot": "M-B-hechuan", "leadGender": "男性", "anchorCharacterId": "hechuan"},
            asset_map=assets,
        )
        self.assertEqual(
            [
                {"characterId": "hechuan", "startSeconds": 0.0, "endSeconds": 3.0},
                {"characterId": "jiangwan", "startSeconds": 4.0, "endSeconds": 7.0},
            ],
            media["identityTimeline"],
        )

    def test_all_approved_r6_portraits_project_as_dynamic_role_previews(self):
        for character in CHARACTER_MAP.values():
            self.assertEqual("ready", character["mediaStatus"])
            self.assertEqual("dynamic-portrait", character["mediaFallbackKind"])
            self.assertEqual(f"/media/video/CHAR-{character['id']}-portrait.mp4", character["video"])

    def test_role_preview_never_projects_unapproved_or_wrong_identity_portrait(self):
        card = CHARACTER_CARD_MAP["peiran"]
        unsafe_assets = (
            {"CHAR-peiran-portrait": {"path": "/media/video/rejected.mp4", "status": "rejected", "identityCast": ["peiran"]}},
            {"CHAR-peiran-portrait": {"path": "/media/video/wrong-person.mp4", "status": "approved-runtime", "identityCast": ["chengye"]}},
        )
        for assets in unsafe_assets:
            with patch("backend.game_content.RUNTIME_ASSET_MAP", assets):
                projected = _public_character(card)
            self.assertEqual("", projected["video"])
            self.assertEqual("planned", projected["mediaStatus"])

    def test_wrong_gender_rotation_is_rejected_to_player_static_safe_fallback(self):
        assets = {
            "D1-A2-villa-entry--rotation-M-A-chengye": {
                "path": "/media/video/wrong-gender.mp4", "status": "approved-runtime", "leadGender": "男性",
            },
        }
        media = resolve_identity_safe_media(
            "D1-A2-villa-entry", "jiangmi", [], current_cast_ids=list(LEGACY_CAST_IDS),
            rotation={"slot": "M-A-chengye", "leadGender": "男性", "anchorCharacterId": "chengye"},
            asset_map=assets,
        )
        self.assertEqual("CHAR-jiangmi-portrait", media["assetId"])
        self.assertEqual(["jiangmi"], media["identityCast"])
        self.assertFalse(media["audioAvailable"])
        self.assertNotEqual("/media/video/wrong-gender.mp4", media["src"])

    def test_legacy_snapshot_migration_is_idempotent_and_preserves_original_cast(self):
        old = _create_snapshot("ENFP", "jiangmi")
        old.pop("castIds", None)
        old.pop("mediaRotation", None)
        once = migrate_snapshot(old)
        twice = migrate_snapshot(once)
        self.assertEqual(list(LEGACY_CAST_IDS), once["castIds"])
        self.assertEqual(once["castIds"], twice["castIds"])
        self.assertEqual(once["relationships"], twice["relationships"])
        self.assertEqual(once["revision"], twice["revision"])

    def test_self_and_out_of_cast_agent_turns_are_rejected(self):
        snapshot = _create_snapshot("INTJ", "luyao")
        with self.assertRaisesRegex(ValueError, "不能和自己私聊"):
            commit_agent_turn(snapshot, "luyao", "你好。", valid_turn(CHARACTER_CARD_MAP["luyao"]))
        outsider_id = next(character_id for character_id in CHARACTER_MAP if character_id not in active_cast_ids(snapshot))
        with self.assertRaisesRegex(ValueError, "不在本季八人名单"):
            commit_agent_turn(snapshot, outsider_id, "你好。", valid_turn(CHARACTER_CARD_MAP[outsider_id]))

    def test_all_sixteen_cards_have_interop_contract(self):
        self.assertEqual(16, len(CHARACTER_CARDS))
        for card in CHARACTER_CARDS[:8]:
            self.assertEqual(set(RELATIONSHIP_AXES), set(card["agentPolicy"]["deltaBounds"]))
            self.assertEqual({"analysts", "diplomats", "sentinels", "explorers"}, set(card["interactionStrategies"]) & {"analysts", "diplomats", "sentinels", "explorers"})
            self.assertGreaterEqual(len(card["fewShots"]), 2)
            self.assertIn(card["eventPolicy"]["eventId"], card["agentPolicy"]["allowedEventIds"])
            self.assertIn(card["sourceProfile"]["alignment"], {"exact", "name-adapted", "runtime-original", "type-adapted", "name-and-type-adapted"})
            self.assertTrue(card["cognitiveStyle"]["decisionRule"])
            self.assertTrue(card["knowledge"]["doesNotKnow"])
            self.assertEqual({"supportive", "probing", "challenging", "boundaryViolation"}, set(card["reactionMatrix"]))
            self.assertIn("新事实", card["dialoguePolicy"]["mustAdvanceBy"])

    def test_public_identity_cards_use_confirmed_occupation_or_explicit_holdback(self):
        expected = {
            "shenmo": "投行VP", "linyu": "建筑工程师", "chengye": "极限运动品牌创始人",
            "guyan": "游戏策划/外包", "jiangwan": "心理咨询师", "jiangmi": "职业待公开",
            "sunnian": "插画师", "chensu": "职业待公开",
            "luyao": "智能硬件产品负责人", "yecheng": "古籍修复师",
            "tangli": "户外纪录片现场制片人", "wenxu": "城市气候数据研究员",
            "hechuan": "纪录片剪辑师", "peiran": "儿童博物馆体验策展人",
            "lichuan": "精品酒店餐饮运营经理", "qiaolan": "舞台机械工程师",
        }
        self.assertEqual(expected, {character_id: character["occupation"] for character_id, character in CHARACTER_MAP.items()})
        self.assertIsNone(CHARACTER_MAP["jiangmi"]["age"])
        self.assertEqual(29, CHARACTER_MAP["shenmo"]["age"])

    def test_deepseek_delta_is_bounded_by_each_card(self):
        for card in CHARACTER_CARDS:
            snapshot = snapshot_with_character(card["id"])
            turn = valid_turn(card)
            next_snapshot, _ = commit_agent_turn(snapshot, card["id"], "这是一次具体表达。", turn)
            for axis in RELATIONSHIP_AXES:
                self.assertLessEqual(next_snapshot["relationships"][card["id"]][axis], card["agentPolicy"]["deltaBounds"][axis][1])

    def test_day_one_is_a_guided_plain_language_flow(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        self.assertEqual("arrival-context", snapshot["nodeId"])
        for choice_id, expected in (
            ("context-meet", "villa-arrival"),
            ("arrival-help-luggage", "introductions"),
            ("intro-clear", "cast-first-impressions"),
        ):
            snapshot, _ = apply_choice(snapshot, choice_id)
            self.assertEqual(expected, snapshot["nodeId"])
        transition = project_view(snapshot)["node"]
        self.assertGreaterEqual(len(transition["textBeats"]), 3)
        self.assertIn("其余七", transition["text"])
        self.assertEqual(3, len(transition["choices"]))
        for choice in transition["choices"]:
            self.assertIn(CHARACTER_MAP[choice["targetCharacterId"]]["name"], choice["label"])
        snapshot, impression_receipt = apply_choice(snapshot, transition["choices"][0]["id"])
        self.assertEqual("icebreaker-choice", snapshot["nodeId"])
        self.assertEqual(impression_receipt["targetCharacterId"], snapshot["firstImpressionSeed"]["characterId"])
        self.assertEqual(["team-up", "anonymous-letter", "callback"], snapshot["firstImpressionSeed"]["plannedCallbackNodeIds"])
        projected = project_view(snapshot)
        self.assertEqual(3, len(projected["node"]["choices"]))
        target_ids = [choice["targetCharacterId"] for choice in projected["node"]["choices"]]
        self.assertEqual(3, len(set(target_ids)))
        self.assertNotIn("jiangmi", target_ids)
        snapshot, receipt = apply_choice(snapshot, projected["node"]["choices"][0]["id"])
        target_id = receipt["targetCharacterId"]
        self.assertEqual("guided-chat", snapshot["nodeId"])
        self.assertEqual(target_id, snapshot["guidedTargetCharacterId"])
        self.assertEqual("required", snapshot["pendingInteraction"]["status"])
        with self.assertRaisesRegex(ValueError, "完成一次"):
            apply_choice(snapshot, "chat-team-direct")
        other_id = next(character_id for character_id in active_cast_ids(snapshot) if character_id not in {target_id, "jiangmi"})
        with self.assertRaisesRegex(ValueError, "这一段先去"):
            commit_agent_turn(snapshot, other_id, "你好。", valid_turn(next(card for card in CHARACTER_CARDS if card["id"] == other_id)))
        target_card = next(card for card in CHARACTER_CARDS if card["id"] == target_id)
        snapshot, receipt = commit_agent_turn(snapshot, target_id, "你好，我也第一次参加这样的节目。", valid_turn(target_card))
        self.assertTrue(receipt["guidedInteractionCompleted"])
        self.assertEqual("completed", snapshot["pendingInteraction"]["status"])
        snapshot, _ = apply_choice(snapshot, "chat-team-together")
        self.assertEqual("team-up", snapshot["nodeId"])
        callback = project_view(snapshot)["node"]["firstImpressionCallback"]
        self.assertEqual(snapshot["firstImpressionSeed"]["characterId"], callback["characterId"])
        self.assertTrue(callback["matchesCurrentFocus"])
        snapshot, _ = apply_choice(snapshot, "team-cooperate")
        self.assertEqual("anonymous-letter", snapshot["nodeId"])
        recipients = project_view(snapshot)["node"]["choices"]
        self.assertEqual(3, len(recipients))
        self.assertNotIn("jiangmi", {choice["characterId"] for choice in recipients})
        snapshot, _ = apply_choice(snapshot, recipients[0]["id"], recipients[0]["characterId"])
        self.assertEqual("callback", snapshot["nodeId"])

    def test_every_active_day_one_story_node_has_three_engine_owned_choices(self):
        for node_id in ("arrival-context", "villa-arrival", "introductions", "cast-first-impressions", "icebreaker-choice", "guided-chat", "team-up"):
            self.assertEqual(3, len(NODES[node_id]["choices"]), node_id)
            self.assertEqual(3, len({choice["id"] for choice in NODES[node_id]["choices"]}))
            for choice in NODES[node_id]["choices"]:
                self.assertTrue(choice["intentId"])
                self.assertIn(choice["next"], NODES)

    def test_all_day_one_nodes_project_engine_owned_media_contract(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        for node_id in NODES:
            snapshot["nodeId"] = node_id
            view = project_view(snapshot)
            media = view["mediaContext"]
            contract = DAY1_MEDIA_CONTRACT[node_id]
            self.assertEqual(contract["eventId"], media["eventId"])
            allowed_asset_ids = {
                contract["assetId"],
                *contract.get("variantAssetIds", {}).values(),
                f"CHAR-{snapshot['player']['perspectiveCharacterId']}-portrait",
            }
            self.assertTrue(
                media["assetId"] in allowed_asset_ids
                or media["assetId"].startswith("CHAR-")
                or media["assetId"].startswith(f"{contract['assetId']}--rotation-")
            )
            if media["assetId"].startswith("CHAR-"):
                self.assertEqual("identity-safe-fallback", media["status"])
                self.assertEqual(1, len(media["identityCast"]))
            if media["available"]:
                self.assertTrue(media["src"].startswith("/media/video/"))
                self.assertEqual(media["src"], view["node"]["cinematic"])
            else:
                self.assertEqual("", media["src"])
                self.assertEqual("", media["poster"])
                self.assertIsNone(view["node"]["cinematic"])
                self.assertTrue(media["plannedSrc"].startswith("/media/video/"))
                self.assertTrue(media["plannedPoster"].startswith("/media/posters/"))
            self.assertIn("fallback", media)
            self.assertEqual(media, view["node"]["media"])

    def test_character_specific_media_variants_only_route_when_identity_matches(self):
        assets = {
            "D1-A6-first-dinner-team": {"path": "/media/video/D1-A6-first-dinner-team.mp4", "status": "ready"},
            "D1-A6-first-dinner-team--pair-shenmo-jiangmi": {
                "path": "/media/video/D1-A6-first-dinner-team--pair-shenmo-jiangmi.mp4",
                "status": "ready", "identityCast": ["jiangmi", "shenmo"], "identityScope": "pair",
            },
            "D1-A7-heart-message": {"path": "/media/video/D1-A7-heart-message.mp4", "status": "ready"},
            "D1-A7-heart-message--p-jiangmi": {
                "path": "/media/video/D1-A7-heart-message--p-jiangmi.mp4",
                "status": "ready", "identityCast": ["jiangmi"], "identityScope": "single",
            },
        }
        snapshot = create_snapshot("ENFP", "jiangmi")
        with patch("backend.game_content._runtime_asset_map", return_value=assets):
            snapshot["nodeId"] = "team-up"
            snapshot["guidedTargetCharacterId"] = "shenmo"
            team_media = project_view(snapshot)["mediaContext"]
            self.assertEqual("D1-A6-first-dinner-team--pair-shenmo-jiangmi", team_media["assetId"])
            self.assertEqual("jiangmi", team_media["variantForCharacterId"])
            snapshot["nodeId"] = "anonymous-letter"
            letter_media = project_view(snapshot)["mediaContext"]
            self.assertEqual("D1-A7-heart-message--p-jiangmi", letter_media["assetId"])
            self.assertEqual("jiangmi", letter_media["variantForCharacterId"])

    def test_unapproved_media_never_routes_as_runtime_cinematic(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "arrival-context"
        assets = {
            "D1-A1-island-hotel-establish": {
                "path": "/media/video/D1-A1-island-hotel-establish.mp4",
                "poster": "/media/posters/D1-A1-island-hotel-establish.jpg",
                "status": "provisional-approved",
            }
        }
        with patch("backend.game_content._runtime_asset_map", return_value=assets):
            view = project_view(snapshot)
        self.assertTrue(view["mediaContext"]["available"])
        self.assertEqual("identity-safe-fallback", view["mediaContext"]["status"])
        self.assertEqual("CHAR-jiangmi-portrait", view["mediaContext"]["assetId"])
        self.assertNotEqual(assets["D1-A1-island-hotel-establish"]["path"], view["mediaContext"]["src"])
        self.assertEqual(view["mediaContext"]["src"], view["node"]["cinematic"])

    def test_non_jiangmi_perspectives_never_receive_jiangmi_only_event_footage(self):
        assets = {
            "D1-A2-villa-entry": {
                "path": "/media/video/D1-A2-villa-entry.mp4", "status": "approved-runtime",
                "identityCast": ["jiangmi"], "identityScope": "single",
            },
            "CHAR-shenmo-portrait": {"path": "/media/video/CHAR-shenmo-portrait.mp4"},
        }
        snapshot = create_snapshot("INTJ", "shenmo")
        snapshot["nodeId"] = "villa-arrival"
        with patch("backend.game_content._runtime_asset_map", return_value=assets):
            media = project_view(snapshot)["mediaContext"]
        self.assertEqual("CHAR-shenmo-portrait", media["assetId"])
        self.assertEqual(["shenmo"], media["identityCast"])
        self.assertNotEqual("/media/video/D1-A2-villa-entry.mp4", media["src"])

    def test_new_reviewed_intro_supersedes_legacy_unintelligible_r5_clip(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "introductions"

        media = project_view(snapshot)["mediaContext"]

        self.assertTrue(media["assetId"].startswith("D1-A3-cast-introductions--rotation-"))
        self.assertEqual("approved-gender-rotation", media["selectionReason"])
        self.assertEqual("女性", media["leadGender"])
        self.assertTrue(media["identityCast"])
        self.assertEqual(
            "/media/video/D1-A3-cast-introductions--p-jiangmi.mp4",
            media["plannedSrc"],
        )

    def test_legacy_bare_montage_is_superseded_by_gender_rotation(self):
        snapshot = create_snapshot("INTJ", "shenmo")
        snapshot["nodeId"] = "cast-first-impressions"

        media = project_view(snapshot)["mediaContext"]

        self.assertEqual("gender-rotation", media["routingMode"])
        self.assertEqual(active_cast_ids(snapshot), media["requiredIdentityCast"])
        self.assertTrue(media["assetId"].startswith("D1-A3B-cast-first-impressions--rotation-M-"))
        self.assertEqual("男性", media["leadGender"])
        self.assertNotEqual("/media/video/D1-A3B-cast-first-impressions.mp4", media["src"])

    def test_fallback_introductions_are_direct_character_specific_speech(self):
        for card in CHARACTER_CARDS:
            snapshot = create_snapshot(card["mbti"], card["id"])
            flavor = build_fallback_script_flavor(card["id"], active_cast_ids(snapshot))
            introductions = flavor["nodes"]["introductions"]["choices"]
            self.assertEqual(3, len(introductions))
            for choice in introductions:
                self.assertIn(card["names"]["primary"], choice["label"])
                self.assertIn(card["mbti"], choice["label"])
                self.assertTrue(any(marker in choice["label"] for marker in ("来这里", "这七天", "这次", "想看看", "想试试", "参加")))
                self.assertIn("introductionMode", choice)
            validate_day1_script(snapshot, flavor)

    def test_intro_validator_rejects_riddle_and_contextual_node_keeps_engine_ids(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        fallback = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        fallback["nodes"]["introductions"]["choices"][0]["label"] = "我叫姜米，ENFP，其他的先留个秘密，你猜我为什么来。"
        with self.assertRaisesRegex(ValueError, "工作或日常背景|谜语"):
            validate_day1_script(snapshot, fallback)
        valid_node = {"node": build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))["nodes"]["team-up"]}
        normalized = validate_day1_node_script(snapshot, "team-up", valid_node)
        self.assertEqual([item["id"] for item in NODES["team-up"]["choices"]], [item["id"] for item in normalized["choices"]])
        installed = install_day1_node_script(snapshot, "team-up", valid_node, {"provider": "deepseek", "model": "test"})
        self.assertEqual("deepseek-contextual", installed["scriptFlavor"]["contextualNodes"]["team-up"]["source"])

    def test_contextual_node_prompt_contains_protagonist_memory_and_not_media_contract(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "team-up"
        snapshot["guidedTargetCharacterId"] = "shenmo"
        snapshot["echoMemories"].append({"id": "m1", "characterId": "shenmo", "summary": "沈墨记得姜米愿意先说清分工", "interpretation": "她的邀请很具体"})
        prompt = build_day1_node_messages(snapshot, "team-up")[1]["content"]
        self.assertIn('"primary": "姜米"', prompt)
        self.assertIn("沈墨记得姜米愿意先说清分工", prompt)
        self.assertNotIn("/media/video/", prompt)

    def test_perspective_character_cannot_chat_or_receive_own_letter(self):
        snapshot = create_snapshot("ESFJ", "sunnian")
        with self.assertRaisesRegex(ValueError, "不能和自己私聊"):
            commit_agent_turn(snapshot, "sunnian", "你好。", valid_turn(next(card for card in CHARACTER_CARDS if card["id"] == "sunnian")))
        snapshot["nodeId"] = "anonymous-letter"
        with self.assertRaisesRegex(ValueError, "不能把心动短信发给自己"):
            apply_choice(snapshot, "letter-sunnian", "sunnian")
        with self.assertRaisesRegex(ValueError, "本轮给出的三位收信人"):
            apply_choice(snapshot, "letter-luyao", "luyao")

    def test_cold_start_delta_is_clamped_to_one(self):
        for card in CHARACTER_CARDS:
            snapshot = snapshot_with_character(card["id"])
            next_snapshot, _ = commit_agent_turn(snapshot, card["id"], "第一次具体表达。", valid_turn(card))
            for value in next_snapshot["relationships"][card["id"]].values():
                self.assertLessEqual(abs(value), 1)

    def test_old_snapshot_is_migrated_without_losing_scores(self):
        old = create_snapshot("ENFP")
        del old["relationships"]
        del old["eventLedger"]
        old["affection"]["shenmo"] = 4
        migrated = migrate_snapshot(old)
        self.assertEqual(4, migrated["relationships"]["shenmo"]["affection"])
        self.assertEqual([], migrated["eventLedger"])
        self.assertEqual(CONTENT_VERSION, migrated["contentVersion"])

    def test_selected_perspective_is_persisted_and_projected(self):
        snapshot = create_snapshot("ISTP", "chensu")
        self.assertEqual("chensu", snapshot["player"]["perspectiveCharacterId"])
        self.assertEqual("chensu", project_view(snapshot)["node"]["characterId"])

    def test_per_run_script_validator_preserves_ids_and_forbids_self_target(self):
        snapshot = create_snapshot("ESFJ", "jiangmi")
        fallback = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        validated = validate_day1_script(snapshot, fallback)
        self.assertEqual("deepseek", validated["source"])
        self.assertEqual(
            [choice["id"] for choice in NODES["icebreaker-choice"]["choices"]],
            [choice["id"] for choice in validated["nodes"]["icebreaker-choice"]["choices"]],
        )
        injected = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        injected["nodes"]["icebreaker-choice"]["choices"][0]["targetCharacterId"] = "jiangmi"
        with self.assertRaisesRegex(ValueError, "非主角"):
            validate_day1_script(snapshot, injected)
        installed = install_day1_script(snapshot, injected)
        self.assertEqual("fallback", installed["scriptFlavor"]["source"])
        self.assertNotIn("jiangmi", {choice["targetCharacterId"] for choice in installed["scriptFlavor"]["nodes"]["icebreaker-choice"]["choices"]})

    def test_script_validator_rejects_third_person_player_and_mechanical_key_copy(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        third_person = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        third_person["nodes"]["villa-arrival"]["action"] = "姜米拉开椅子，等你决定。"
        with self.assertRaisesRegex(ValueError, "第三人称"):
            validate_day1_script(snapshot, third_person)
        old_task = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        old_task["nodes"]["icebreaker-choice"]["choices"][0]["label"] = "先问第二把钥匙在哪里"
        with self.assertRaisesRegex(ValueError, "旧钥匙任务"):
            validate_day1_script(snapshot, old_task)

    def test_extract_json_accepts_one_object_before_provider_epilogue(self):
        self.assertEqual({"ok": True}, extract_json('{"ok": true}\n以上是完整 JSON。'))

    def test_first_chat_rejects_invented_elapsed_days_and_program_clues(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "guided-chat"
        card = next(card for card in CHARACTER_CARDS if card["id"] == "shenmo")
        turn = valid_turn(card)
        turn["dialogue"] = "我已经数了三天桌签，节目组说里面藏着一条线索。"
        with self.assertRaisesRegex(ValueError, "尚未发生"):
            validate_agent_turn(card, turn, snapshot)

    def test_first_chat_requires_direct_public_introduction(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["jiangwan"]
        turn = valid_turn(card)
        turn["dialogue"] = "我更习惯听别人说。你先告诉我，最近最想留下什么声音？"
        with self.assertRaisesRegex(ValueError, "角色姓名"):
            validate_agent_turn(card, turn, snapshot, "你好。")

    def test_first_opener_cannot_invent_unknown_player_job(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        target = next(card for card in CHARACTER_CARDS if card["id"] == "shenmo")
        player = next(card for card in CHARACTER_CARDS if card["id"] == "jiangmi")
        payload = {
            "opening": "你好，我是沈墨。刚进小屋，我们先从简单的问题开始吧。",
            "stageDirection": "他朝你点了点头",
            "suggestions": ["你好，我叫姜米。", "我是做市场相关工作的。", "你为什么会来这里？"],
        }
        with self.assertRaisesRegex(ValueError, "编造了职业"):
            validate_chat_opening(target, snapshot, payload, player)

    def test_first_opener_stays_in_small_talk_instead_of_clue_hunting(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        target = next(card for card in CHARACTER_CARDS if card["id"] == "shenmo")
        player = next(card for card in CHARACTER_CARDS if card["id"] == "jiangmi")
        payload = {
            "opening": "你好，我是沈墨。刚进小屋，我们先从简单的问题开始吧。",
            "stageDirection": "他朝你点了点头",
            "suggestions": ["你好，我是姜米。", "你现在还紧张吗？", "你刚才是在找什么线索？"],
        }
        with self.assertRaisesRegex(ValueError, "任务或秘密"):
            validate_chat_opening(target, snapshot, payload, player)

    def test_validated_deepseek_cache_installs_without_runtime_generation(self):
        snapshot = create_snapshot("ESFJ", "jiangmi")
        fallback = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        package = {
            "schemaVersion": 1,
            "characterCardContentVersion": CARD_PACKAGE["contentVersion"],
            "generator": {"provider": "deepseek", "model": "test-model"},
            "generatedAt": "2026-08-24T10:00:00+08:00",
            "flavors": {"jiangmi": {"generatedAt": "2026-08-24T10:01:00+08:00", "payload": {"nodes": fallback["nodes"]}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "day1-script.json"
            path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
            installed = install_cached_day1_script(snapshot, path)
        self.assertIsNotNone(installed)
        self.assertEqual("deepseek-cached", installed["scriptFlavor"]["source"])
        self.assertEqual("test-model", installed["scriptFlavor"]["generator"]["model"])
        self.assertEqual(CARD_PACKAGE["contentVersion"], installed["scriptFlavor"]["characterCardContentVersion"])

    def test_runtime_rejects_legacy_cache_after_humanlike_card_upgrade(self):
        package = json.loads((Path(__file__).resolve().parent.parent / "content" / "day1_script_flavors.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(LEGACY_CAST_IDS), set(package["flavors"]))
        for card in CHARACTER_CARDS[:8]:
            snapshot = create_snapshot(card["mbti"], card["id"])
            self.assertIsNone(install_cached_day1_script(snapshot))
            installed = install_day1_script(snapshot, None)
            self.assertEqual("fallback", installed["scriptFlavor"]["source"])
            for choice in installed["scriptFlavor"]["nodes"]["introductions"]["choices"]:
                self.assertIn(card["names"]["primary"], choice["label"])
                self.assertIn(card["mbti"], choice["label"])
                self.assertNotIn("你猜", choice["label"])

    def test_all_live_fallback_introductions_are_spoken_character_lines(self):
        background_anchors = {
            "shenmo": ("投行",), "linyu": ("建筑",), "chengye": ("极限运动",),
            "guyan": ("游戏",), "jiangwan": ("心理咨询",), "jiangmi": ("声音", "录音", "故事"),
            "sunnian": ("插画",), "chensu": ("相机", "修"),
            "luyao": ("智能硬件", "产品"), "yecheng": ("古籍", "修复"),
            "tangli": ("户外纪录片", "现场制片"), "wenxu": ("城市气候", "数据"),
            "hechuan": ("纪录片", "剪辑"), "peiran": ("儿童博物馆", "体验策展"),
            "lichuan": ("精品酒店", "餐饮运营"), "qiaolan": ("舞台机械", "工程"),
        }
        strategy_summaries = ("认真介绍姓名", "介绍完自己", "承认有点紧张", "选择一种方式")
        for card in CHARACTER_CARDS:
            snapshot = create_snapshot(card["mbti"], card["id"])
            snapshot["nodeId"] = "introductions"
            choices = project_view(snapshot)["node"]["choices"]
            self.assertEqual(3, len(choices))
            for choice in choices:
                label = choice["label"]
                self.assertIn(card["names"]["primary"], label)
                self.assertIn(card["mbti"], label)
                self.assertTrue(any(anchor in label for anchor in background_anchors[card["id"]]))
                self.assertTrue(any(marker in label for marker in ("来这里", "来参加", "这次来", "这七天", "我来参加")))
                self.assertFalse(any(summary in label for summary in strategy_summaries))

    def test_all_runtime_fallback_nodes_pass_contextual_surface_contract(self):
        for card in CHARACTER_CARDS[:8]:
            snapshot = create_snapshot(card["mbti"], card["id"])
            installed = install_day1_script(snapshot, None)
            self.assertEqual("fallback", installed["scriptFlavor"]["source"])
            for node_id, node in installed["scriptFlavor"]["nodes"].items():
                snapshot["nodeId"] = node_id
                validate_day1_node_script(snapshot, node_id, {"node": node})

    def test_contextual_transition_requires_ensemble_summary_and_future_hook(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "cast-first-impressions"
        fallback = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))["nodes"]["cast-first-impressions"]
        valid = validate_day1_node_script(snapshot, "cast-first-impressions", {"node": fallback})
        self.assertEqual(4, len(valid["textBeats"]))
        broken = json.loads(json.dumps(fallback, ensure_ascii=False))
        broken["title"] = "客厅重新安静下来"
        broken["text"] = "客厅里重新安静下来。你记住了几个人刚才说话的样子，准备选择一个人继续留意。"
        broken["textBeats"] = ["客厅里重新安静下来。", "你记住了几个人刚才说话的样子。", "现在准备选择一个人继续留意。"]
        broken["action"] = "镜头回到你停在膝上的手。"
        with self.assertRaisesRegex(ValueError, "其余七位"):
            validate_day1_node_script(snapshot, "cast-first-impressions", {"node": broken})

    def test_transition_surface_cannot_redirect_engine_route_or_patch(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "cast-first-impressions"
        payload = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))["nodes"]["cast-first-impressions"]
        payload = json.loads(json.dumps(payload, ensure_ascii=False))
        payload["choices"][0]["next"] = "callback"
        payload["choices"][0]["patch"] = {"flags.heat": 99}
        installed = install_day1_node_script(snapshot, "cast-first-impressions", {"node": payload})
        next_snapshot, receipt = apply_choice(installed, "impression-listener")
        self.assertEqual("icebreaker-choice", next_snapshot["nodeId"])
        self.assertEqual(0, next_snapshot["flags"]["heat"])
        self.assertEqual("impression.remember-listener", receipt["effectIntentId"])

    def test_contextual_icebreaker_requires_plain_completion_rules(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "icebreaker-choice"
        fallback = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))["nodes"]["icebreaker-choice"]
        self.assertEqual(4, len(validate_day1_node_script(snapshot, "icebreaker-choice", {"node": fallback})["textBeats"]))
        broken = json.loads(json.dumps(fallback, ensure_ascii=False))
        broken["text"] = "三张卡放在桌上。你选一张，再去找对应的人聊一会儿。"
        broken["textBeats"] = ["三张卡放在桌上。", "你选一张，再去找对应的人聊一会儿。"]
        with self.assertRaisesRegex(ValueError, "完成条件"):
            validate_day1_node_script(snapshot, "icebreaker-choice", {"node": broken})

    def test_transition_prompt_has_full_protagonist_and_ensemble_context(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "cast-first-impressions"
        prompt = build_day1_node_messages(snapshot, "cast-first-impressions")[1]["content"]
        self.assertIn('"protagonistCard"', prompt)
        self.assertIn('"otherCastCount": 7', prompt)
        self.assertIn('"primary": "姜米"', prompt)
        self.assertIn("其余七位嘉宾继续并完成自我介绍", prompt)
        self.assertNotIn("/media/video/", prompt)

    def test_introduction_rejects_invented_unknown_job(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        flavor = build_fallback_script_flavor("jiangmi", active_cast_ids(snapshot))
        flavor["nodes"]["introductions"]["choices"][0]["label"] = (
            "大家好，我叫姜米，ENFP，平时喜欢录声音日记和写故事，我是声音设计师。"
            "这次来参加，是想看看安静时会不会也有人愿意留下。"
        )
        with self.assertRaisesRegex(ValueError, "未确认职业"):
            validate_day1_script(snapshot, {"nodes": flavor["nodes"]})

    def test_agent_first_chat_rejects_task_only_participation_reason(self):
        snapshot = create_snapshot("ESFJ", "sunnian")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["chensu"]
        turn = valid_turn(card)
        turn["dialogue"] = (
            "你好，我叫陈叙，ISTP，平时喜欢修旧相机。"
            "这次来这里主要想修好一台旧相机，顺便认识大家。你刚才说有点生疏，我也一样。"
        )
        with self.assertRaisesRegex(ValueError, "人物任务"):
            validate_agent_turn(card, turn, snapshot, "你好，我是苏念。")

    def test_agent_mainline_accepts_clear_action_with_natural_word_order(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["sunnian"]
        turn = valid_turn(card)
        turn["suggestions"] = [
            {"type": "followup", "text": "你刚才说整理房间会放松，这个习惯是一直都有的吗？"},
            {"type": "mainline", "text": "要不要一起去厨房看看，今晚我们能准备什么？"},
            {"type": "deeper", "text": "别人第一次见你时，最容易误会你的哪一点？"},
        ]
        validated = validate_agent_turn(card, turn, snapshot, "刚进客厅还有点生疏，不过整理房间会让我放松。")
        self.assertEqual("mainline-gradient", validated["suggestions"][1]["style"])

    def test_agent_suggestion_cannot_turn_future_interest_into_present_fact(self):
        snapshot = create_snapshot("ESFJ", "sunnian")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["chensu"]
        turn = valid_turn(card)
        turn["suggestions"] = [
            {"type": "followup", "text": "你刚才介绍了自己；第一次见这么多人，现在最想先聊什么？"},
            {"type": "mainline", "text": "要不要一起去厨房准备晚餐，我们先商量分工？"},
            {"type": "deeper", "text": "你带的那台旧相机，最想拍下谁？"},
        ]
        with self.assertRaisesRegex(ValueError, "已发生事实"):
            validate_agent_turn(card, turn, snapshot, "你好，我是苏念。")

    def test_agent_prompt_knows_first_meeting_and_reopening(self):
        snapshot = create_snapshot("INFP", "jiangmi")
        card = next(card for card in CHARACTER_CARDS if card["id"] == "shenmo")
        first_prompt = build_agent_messages(card, snapshot, "你好")[1]["content"]
        self.assertIn('"isFirstConversation": true', first_prompt)
        self.assertIn('"requiredOpeningPrefix": "我叫沈墨，INTJ，在投行做VP。"', first_prompt)
        opening = fallback_chat_opening(card, snapshot)
        self.assertIn("沈墨", opening["opening"])
        self.assertEqual("first-meeting", validate_chat_opening(card, snapshot, opening)["mode"])
        snapshot, _ = commit_agent_turn(snapshot, "shenmo", "你好，我叫姜米。", valid_turn(card))
        reopened = fallback_chat_opening(card, snapshot)
        self.assertEqual("reopening", reopened["mode"])
        self.assertIn("上次", reopened["opening"])

    def test_agent_prompt_retrieves_only_current_character_few_shots(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        shenmo = CHARACTER_CARD_MAP["shenmo"]
        linyu = CHARACTER_CARD_MAP["linyu"]
        shenmo_prompt = build_agent_messages(shenmo, snapshot, "我不会催你回答。", CHARACTER_CARD_MAP["jiangmi"])[1]["content"]
        linyu_prompt = build_agent_messages(linyu, snapshot, "我不会催你回答。", CHARACTER_CARD_MAP["jiangmi"])[1]["content"]
        self.assertIn('"retrievedFewShotStructures"', shenmo_prompt)
        self.assertIn('"characterId": "shenmo"', shenmo_prompt)
        self.assertIn('"retrievedPlayerStrategyFewShotStructures"', shenmo_prompt)
        self.assertIn('"characterId": "jiangmi"', shenmo_prompt)
        self.assertIn('"characterId": "linyu"', linyu_prompt)
        self.assertNotEqual(shenmo_prompt, linyu_prompt)
        self.assertNotIn('"microExcerpt"', shenmo_prompt)
        source_line = shenmo["researchAnchors"][0].get("microExcerpt")
        if source_line:
            self.assertNotIn(source_line, shenmo_prompt)
        self.assertNotIn(linyu["fewShots"][0]["reply"], shenmo_prompt)

    def test_agent_turn_returns_typed_suggestions_and_legacy_projection(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["shenmo"]
        turn = valid_turn(card)
        turn["suggestions"] = [
            {"type": "followup", "text": "你刚才说会先想清楚，哪一步最难开口？"},
            {"type": "mainline", "text": "沈墨，要不要和我一起准备晚餐？我们先商量分工。"},
            {"type": "deeper", "text": "如果没有镜头，你通常怎样让一个人知道你在意？"},
        ]
        validated = validate_agent_turn(card, turn, snapshot, "我也会先想清楚。")
        self.assertEqual(["followup", "mainline", "deeper"], [item["type"] for item in validated["suggestions"]])
        self.assertEqual("mainline-gradient", validated["suggestions"][1]["style"])
        self.assertEqual([item["text"] for item in validated["suggestions"]], validated["suggestedPrompts"])
        prompt = build_agent_messages(card, snapshot, "我也会先想清楚。", CHARACTER_CARD_MAP["jiangmi"])[1]["content"]
        self.assertIn('"playerVoiceForSuggestions"', prompt)
        self.assertIn('"type": "mainline"', prompt)

    def test_suggestion_fallback_is_grounded_and_rejects_fake_player_quote(self):
        snapshot = snapshot_with_character("jiangmi")
        snapshot["nodeId"] = "guided-chat"
        snapshot["echoMemories"].append({
            "characterId": "jiangmi", "agentReply": "我们先聊眼前这件事。",
            "summary": "双方已完成第一次问候",
        })
        card = CHARACTER_CARD_MAP["jiangmi"]
        fallback_payload = valid_turn(card)
        fallback_payload["dialogue"] = "我留下，是想知道安静坐在一个人身边时，我们还愿不愿意继续认识彼此。"
        fallback_payload["proposedEventId"] = None
        fallback_payload.pop("suggestions", None)
        validated = validate_agent_turn(
            card, fallback_payload, snapshot,
            "我不想听节目里的标准答案。你为什么还留在这里？",
        )
        self.assertNotIn("这个点子很好玩", validated["suggestions"][0]["text"])
        self.assertIn("刚才回答", validated["suggestions"][0]["text"])

        fake_quote = dict(fallback_payload)
        fake_quote["suggestions"] = [
            {"type": "followup", "text": "你刚才说这个点子很好玩，那最想留下哪一步？"},
            {"type": "mainline", "text": "姜米，要不要一起去厨房准备晚餐？我们先商量分工。"},
            {"type": "deeper", "text": "安静下来以后，你最希望身边的人做什么？"},
        ]
        with self.assertRaisesRegex(ValueError, "捏造"):
            validate_agent_turn(
                card, fake_quote, snapshot,
                "我不想听节目里的标准答案。你为什么还留在这里？",
            )

    def test_agent_mainline_suggestion_must_return_to_current_goal(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["shenmo"]
        turn = valid_turn(card)
        turn["suggestions"] = [
            {"type": "followup", "text": "你刚才停了一下，是哪句话还没说完？"},
            {"type": "mainline", "text": "我们以后慢慢聊。"},
            {"type": "deeper", "text": "你平时怎样确认自己真的在意一个人？"},
        ]
        with self.assertRaisesRegex(ValueError, "当前剧情目标"):
            validate_agent_turn(card, turn, snapshot, "你好。")

    def test_agent_followup_must_connect_to_last_exchange(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "guided-chat"
        card = CHARACTER_CARD_MAP["shenmo"]
        turn = valid_turn(card)
        turn["suggestions"] = [
            {"type": "followup", "text": "你平时喜欢什么颜色？"},
            {"type": "mainline", "text": "要不要和我一起准备晚餐？我们可以先商量分工。"},
            {"type": "deeper", "text": "你遇到分歧时通常会先做什么？"},
        ]
        with self.assertRaisesRegex(ValueError, "没有承接"):
            validate_agent_turn(card, turn, snapshot, "我会先把分工写下来。")

    def test_female_fallback_opening_uses_card_pronoun_and_hides_unknown_job(self):
        snapshot = create_snapshot("INTJ", "shenmo")
        card = next(card for card in CHARACTER_CARDS if card["id"] == "jiangmi")
        opening = fallback_chat_opening(card, snapshot)
        self.assertTrue(opening["stageDirection"].startswith("她"))
        self.assertNotIn("待剧情", opening["opening"])

    def test_male_prompt_adds_romance_calibration_and_contextual_memory(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["agentConversations"]["linyu"] = {
            "turnCount": 2,
            "topicLedger": [{"topic": "果汁口味"}, {"topic": "为什么来节目"}],
        }
        runtime_context = normalize_conversation_context(
            snapshot,
            {"time": "DAY 1 · 19:12", "locationId": "hotel-entrance", "channel": "1v1"},
            ["jiangmi", "linyu"],
        )
        prompt = build_agent_messages(
            CHARACTER_CARD_MAP["linyu"], snapshot, "我今天有点紧张。",
            CHARACTER_CARD_MAP["jiangmi"], runtime_context,
        )[1]["content"]
        self.assertIn('"applies": true', prompt)
        self.assertIn('"locationName": "酒店玄关"', prompt)
        self.assertIn("果汁口味", prompt)
        self.assertIn("禁止直男式盘问", build_agent_messages(
            CHARACTER_CARD_MAP["linyu"], snapshot, "我今天有点紧张。",
            CHARACTER_CARD_MAP["jiangmi"], runtime_context,
        )[0]["content"])
        self.assertIn('"humanSpeechContract"', prompt)
        self.assertIn('"romanticIntelligenceContract"', prompt)
        system = build_agent_messages(
            CHARACTER_CARD_MAP["linyu"], snapshot, "我今天有点紧张。",
            CHARACTER_CARD_MAP["jiangmi"], runtime_context,
        )[0]["content"]
        self.assertIn("真人不会平均回应", system)
        self.assertIn("不得把女性的主动写成等待男性评判", system)

    def test_agent_validator_rejects_ai_summary_and_fake_disfluency(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        card = CHARACTER_CARD_MAP["linyu"]
        ai_summary = valid_turn(card)
        ai_summary["dialogue"] = "听起来你似乎有点紧张，我能感觉到这件事对你很重要。"
        with self.assertRaisesRegex(ValueError, "明显 AI 味"):
            validate_agent_turn(card, ai_summary, snapshot, "刚进来确实有点紧张。")
        fake_human = valid_turn(card)
        fake_human["dialogue"] = "我……那个，就是……怎么说呢……先这样吧。"
        with self.assertRaisesRegex(ValueError, "机械堆叠"):
            validate_agent_turn(card, fake_human, snapshot, "你怎么突然不说话了？")

    def test_chat_opening_prompt_uses_same_human_speech_and_romance_contract(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        messages = build_chat_opening_messages(
            CHARACTER_CARD_MAP["linyu"], snapshot, CHARACTER_CARD_MAP["jiangmi"],
        )
        payload = json.loads(messages[1]["content"])
        self.assertIn("humanSpeechContract", payload["context"])
        self.assertIn("romanticIntelligenceContract", payload["context"])
        retrieved = payload["context"]["retrievedFewShotStructures"]
        self.assertEqual("linyu", retrieved["characterId"])
        self.assertGreaterEqual(len(retrieved["items"]), 2)
        self.assertLessEqual(len(retrieved["items"]), 3)
        player_strategy = payload["context"]["retrievedPlayerStrategyFewShotStructures"]
        self.assertEqual("jiangmi", player_strategy["characterId"])
        self.assertGreaterEqual(len(player_strategy["items"]), 2)
        self.assertIn("只注意一个现场细节", messages[0]["content"])

    def test_day1_node_prompt_retrieves_protagonist_few_shots_without_source_quote(self):
        snapshot = _create_snapshot("ISTP", "qiaolan")
        payload = json.loads(build_day1_node_messages(snapshot, "team-up")[1]["content"])
        context = payload["context"]
        retrieved = context["retrievedFewShotStructures"]
        self.assertEqual("qiaolan", retrieved["characterId"])
        self.assertGreaterEqual(len(retrieved["items"]), 2)
        self.assertLessEqual(len(retrieved["items"]), 3)
        self.assertNotIn("fewShots", context["protagonistCard"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("microExcerpt", serialized)
        source_line = CHARACTER_CARD_MAP["qiaolan"]["researchAnchors"][0].get("microExcerpt")
        if source_line:
            self.assertNotIn(source_line, serialized)

    def test_repeat_detector_blocks_copy_and_return_to_opening_topic(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["echoMemories"] = [
            {"characterId": "linyu", "agentReply": "我也记住了你说的橙汁。今晚备菜时，我把冰箱第二格留给你。"},
            {"characterId": "linyu", "agentReply": "厨房见。香菜我会单独放，不替你决定。"},
        ]
        self.assertIsNotNone(detect_repetitive_agent_reply(
            snapshot, "linyu", "我也记住了你说的橙汁。今晚备菜时，我把冰箱第二格留给你。",
        ))
        self.assertIn("开场", detect_repetitive_agent_reply(snapshot, "linyu", "所以你为什么会来这里？") or "")

    def test_repeat_detector_accepts_legacy_string_topic_ledger(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["agentConversations"]["linyu"] = {
            "turnCount": 1,
            "topicLedger": ["集体自我介绍与参加来意"],
        }
        self.assertIsNone(detect_repetitive_agent_reply(
            snapshot, "linyu", "我想先把今晚的备菜分工说清楚。",
        ))

    def test_agent_turn_rejects_task_only_stay_reason_and_impossible_time(self):
        snapshot = snapshot_with_character("qiaolan")
        snapshot["nodeId"] = "guided-chat"
        snapshot["echoMemories"].append({
            "characterId": "qiaolan", "agentReply": "我们先从眼前的小事聊。",
            "summary": "双方已完成第一次问候",
        })
        card = CHARACTER_CARD_MAP["qiaolan"]
        task_only = valid_turn(card)
        task_only["dialogue"] = "我留下，是因为休息室的灯架还没修好。现在我会先把它固定住。"
        with self.assertRaisesRegex(ValueError, "与人和关系"):
            validate_agent_turn(card, task_only, snapshot, "你为什么还留在这里？")
        relational = valid_turn(card)
        relational["dialogue"] = "我留下，是想看看有没有人愿意跟我一起把一件小事做完，而不是只听我讲完就点头。"
        relational["proposedEventId"] = None
        self.assertEqual(
            relational["dialogue"],
            validate_agent_turn(card, relational, snapshot, "你为什么还留在这里？")["dialogue"],
        )
        impossible_time = valid_turn(card)
        impossible_time["dialogue"] = "我想继续认识你，也想和你互相照顾。今晚早餐我们一人负责一半。"
        with self.assertRaisesRegex(ValueError, "时间矛盾"):
            validate_agent_turn(card, impossible_time, snapshot, "那我们接下来做什么？")

    def test_contextual_turn_records_who_when_where_and_topic(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        card = CHARACTER_CARD_MAP["linyu"]
        context = normalize_conversation_context(
            snapshot, {"time": "DAY 1 · 18:26", "locationId": "hotel-entrance"}, ["jiangmi", "linyu"],
        )
        turn = valid_turn(card)
        turn["topicSummary"] = "第一次聊厨房分工"
        state, receipt = commit_agent_turn(snapshot, "linyu", "你好，晚餐要一起准备吗？", turn, context)
        memory = state["echoMemories"][-1]
        self.assertEqual("酒店玄关", memory["locationName"])
        self.assertEqual("DAY 1 · 18:18", memory["time"])
        self.assertEqual(["姜米", "林屿"], memory["participantNames"])
        self.assertEqual("1v1", memory["channel"])
        self.assertEqual("第一次聊厨房分工", state["agentConversations"]["linyu"]["topicLedger"][-1]["topic"])
        self.assertEqual(memory["conversationId"], state["conversationHistory"][-1]["conversationId"])
        self.assertEqual("酒店玄关", receipt["context"]["locationName"])
        history_turn = state["conversationHistory"][-1]["turns"][0]
        self.assertEqual("linyu", history_turn["characterId"])
        self.assertEqual("姜米", history_turn["playerCharacterName"])
        self.assertEqual("你好，晚餐要一起准备吗？", history_turn["playerText"])
        self.assertEqual(memory["agentReply"], history_turn["agentReply"])
        self.assertEqual("第一次聊厨房分工", history_turn["topicSummary"])

    def test_location_filter_and_group_context_contract(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        contexts = available_chat_contexts(snapshot)
        entrance = next(item for item in contexts["venues"] if item["locationId"] == "hotel-entrance")
        self.assertEqual(7, len(entrance["characters"]))
        participants = ["jiangmi", entrance["characters"][0]["id"], entrance["characters"][1]["id"]]
        group = normalize_conversation_context(
            snapshot, {"locationId": "hotel-entrance", "channel": "group"}, participants, "group",
        )
        self.assertEqual("group", group["channel"])
        self.assertEqual(3, len(group["participantIds"]))
        self.assertTrue(contexts["availableGroupChats"])
        self.assertIn("participantIds", contexts["availableGroupChats"][0])

    def test_group_turns_share_one_who_when_where_what_ledger(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        participants = ["jiangmi", "linyu", "chengye"]
        context = normalize_conversation_context(
            snapshot, {"locationId": "hotel-entrance", "channel": "group"}, participants, "group",
        )
        linyu_turn = valid_turn(CHARACTER_CARD_MAP["linyu"])
        linyu_turn["topicSummary"] = "三人聊第一顿晚餐"
        snapshot, _ = commit_agent_turn(snapshot, "linyu", "我们三个人晚餐要不要一起搭手？", linyu_turn, context)
        chengye_turn = valid_turn(CHARACTER_CARD_MAP["chengye"])
        chengye_turn["topicSummary"] = "程野提议分配备菜"
        snapshot, _ = commit_agent_turn(snapshot, "chengye", "我们三个人晚餐要不要一起搭手？", chengye_turn, context)

        self.assertEqual(1, len(snapshot["conversationHistory"]))
        history = snapshot["conversationHistory"][0]
        self.assertEqual("group", history["channel"])
        self.assertEqual(["姜米", "林屿", "程野"], history["participantNames"])
        self.assertEqual(2, history["turnCount"])
        self.assertEqual(["linyu", "chengye"], [turn["characterId"] for turn in history["turns"]])
        self.assertTrue(all(turn["locationName"] == "酒店玄关" for turn in history["turns"]))
        prompt = build_agent_messages(
            CHARACTER_CARD_MAP["chengye"], snapshot, "那就这么定。", CHARACTER_CARD_MAP["jiangmi"], context,
        )[1]["content"]
        self.assertIn(chengye_turn["dialogue"], prompt)
        self.assertIn("程野提议分配备菜", prompt)

    def test_conversation_id_cannot_be_reused_with_different_context(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        context = normalize_conversation_context(
            snapshot, {"locationId": "hotel-entrance"}, ["jiangmi", "linyu"], "1v1",
        )
        turn = valid_turn(CHARACTER_CARD_MAP["linyu"])
        turn["topicSummary"] = "玄关初次打招呼"
        snapshot, _ = commit_agent_turn(snapshot, "linyu", "你好。", turn, context)
        with self.assertRaisesRegex(ValueError, "地点、频道或参与者"):
            normalize_conversation_context(
                snapshot,
                {"conversationId": context["conversationId"], "locationId": "living-room"},
                ["jiangmi", "linyu"], "1v1",
            )

    def test_male_validator_rejects_dry_errand_and_reused_topic(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["echoMemories"] = [
            {"characterId": "linyu", "agentReply": "刚才我们聊过第一顿晚餐。"},
            {"characterId": "linyu", "agentReply": "你说想喝点东西，我记住了。"},
        ]
        snapshot["agentConversations"]["linyu"] = {
            "turnCount": 2, "topicLedger": [{"topic": "果汁口味"}],
        }
        dry = valid_turn(CHARACTER_CARD_MAP["linyu"])
        dry["dialogue"] = "好，你想喝什么口味？我去拿，橙汁还是别的都可以。"
        dry["topicSummary"] = "跑腿拿果汁"
        with self.assertRaisesRegex(ValueError, "只是确认偏好和跑腿"):
            validate_agent_turn(CHARACTER_CARD_MAP["linyu"], dry, snapshot, "我有点渴。")
        richer = valid_turn(CHARACTER_CARD_MAP["linyu"])
        richer["dialogue"] = "我刚才差点把无糖气泡水认成洗洁精，幸好没抢着表现。你要橙汁的话我们一起去拿，顺便救我一次。"
        richer["topicSummary"] = "果汁口味"
        with self.assertRaisesRegex(ValueError, "话题摘要重复"):
            validate_agent_turn(CHARACTER_CARD_MAP["linyu"], richer, snapshot, "我想喝橙汁。")

    def test_normal_choice_persists_bounded_free_input_for_next_script_only(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        choice = NODES["arrival-context"]["choices"][0]
        original_flags = dict(snapshot["flags"])
        state, receipt = apply_choice(
            snapshot, choice["id"], custom_text="我先把行李放稳，再笑着和门口的人打招呼。",
        )
        self.assertEqual("custom", receipt["playerExpression"]["mode"])
        self.assertEqual(receipt["customText"], receipt["playerExpression"]["text"])
        self.assertEqual(choice["intentId"], receipt["effectIntentId"])
        expected_heat = original_flags["heat"] + int(choice.get("patch", {}).get("flags.heat", 0))
        self.assertEqual(expected_heat, state["flags"]["heat"])
        prompt_payload = json.loads(build_day1_node_messages(state, state["nodeId"])[1]["content"])
        stored = prompt_payload["context"]["choiceHistory"][-1]
        self.assertEqual(receipt["customText"], stored["customText"])
        self.assertEqual(receipt["playerExpression"], stored["playerExpression"])
        with self.assertRaisesRegex(ValueError, "2-160"):
            apply_choice(snapshot, choice["id"], custom_text="太长" * 81)

    def test_heart_message_accepts_custom_text_and_returns_inbox_body(self):
        snapshot = create_snapshot("ENFP", "jiangmi")
        snapshot["nodeId"] = "anonymous-letter"
        recipients = project_view(snapshot)["node"]["choices"]
        recipient_id = recipients[0]["characterId"]
        self.assertEqual(3, len(heart_message_suggestions(snapshot, recipient_id)))
        state, receipt = apply_choice(
            snapshot, recipients[0]["id"], recipient_id,
            custom_text="今天一起准备晚餐很开心，明天还想和你聊聊。",
        )
        self.assertEqual("custom", receipt["heartMessage"]["source"])
        self.assertEqual(receipt["heartMessage"]["text"], receipt["heartMessage"]["body"])
        self.assertTrue(receipt["heartMessage"]["recipientName"])
        self.assertEqual("callback", state["nodeId"])
        view = project_view(state)
        inbox = view["node"]["heartInbox"]
        self.assertEqual("phone", inbox["device"])
        self.assertGreaterEqual(inbox["unreadCount"], 1)
        self.assertTrue(inbox["messages"][0]["text"])
        self.assertEqual(inbox["messages"][0]["text"], inbox["messages"][0]["body"])
        self.assertEqual(1, view["heartMailbox"]["sentCount"])
        self.assertEqual(1, view["heartMailbox"]["receivedCount"])
        self.assertEqual(state["heartMailbox"], view["snapshot"]["heartMailbox"])


if __name__ == "__main__":
    unittest.main()
