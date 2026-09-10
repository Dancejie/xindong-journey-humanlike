"""Custom identities share the engine, not other users' profiles or guest media."""
import asyncio
import json
import unittest
from copy import deepcopy
from uuid import uuid4

from backend.custom_characters import build_player_card
from backend.game_content import (
    CHARACTER_CARDS, CHARACTER_CARD_MAP, CHARACTER_MAP, DAY1_MEDIA_CONTRACT,
    active_cast_ids, apply_choice, available_chat_contexts, character_scope,
    commit_agent_turn, create_snapshot, day1_media_context, migrate_snapshot,
    normalize_conversation_context, player_card_for, project_view,
)
from backend.agent_prompt import build_agent_messages, build_chat_opening_messages, runtime_character_card
from backend.day1_script import (
    build_day1_node_messages, build_day1_script_messages, install_cached_day1_script,
    install_day1_script, _validate_introduction_choice, validate_day1_node_script,
)
from backend.story_director import STORY_EVENTS, build_story_director_messages, eligible_story_events, resolve_story_event_media
from backend.test_game_content import valid_turn


def custom_card(mbti="ISTP", gender="女性", name="云青"):
    template = next(card for card in CHARACTER_CARDS if card["mbti"] == mbti and card["identity"]["gender"] == gender)
    return build_player_card({
        "name": name, "mbti": mbti, "gender": "female" if gender == "女性" else "male",
        "age": 28, "occupation": "产品设计师", "about": "住在上海，休息时喜欢散步",
        "preferences": "不要在饮料里放香菜", "boundaries": "不要突然拥抱我",
    }, f"custom-{uuid4()}", "/api/custom-media/owner-opaque-photo", template)


def custom_snapshot(card=None):
    card = card or custom_card()
    return create_snapshot(card["mbti"], card["id"], custom_player_card=card)


class CustomPlayerEngineTests(unittest.TestCase):
    def test_all_16_types_and_both_genders_keep_balanced_eight_person_cast(self):
        for mbti in sorted({card["mbti"] for card in CHARACTER_CARDS}):
            for gender in ("男性", "女性"):
                with self.subTest(mbti=mbti, gender=gender):
                    card = custom_card(mbti, gender)
                    state = custom_snapshot(card)
                    view = project_view(state)
                    self.assertEqual(8, len(active_cast_ids(state)))
                    self.assertEqual(7, sum(character["chatEnabled"] for character in view["characters"]))
                    self.assertEqual(4, sum(character["gender"] == "男性" for character in view["characters"]))
                    self.assertEqual(4, sum(character["gender"] == "女性" for character in view["characters"]))
                    self.assertEqual("云青", view["snapshot"]["player"]["displayName"])
                    self.assertEqual(card["id"], view["snapshot"]["player"]["customCharacterId"])
                    self.assertNotIn(card["id"], CHARACTER_MAP)
        self.assertEqual(32, len(CHARACTER_MAP))
        self.assertEqual(32, len(CHARACTER_CARD_MAP))

    def test_migration_restart_and_public_projection_keep_owned_identity(self):
        state = custom_snapshot()
        restored = migrate_snapshot(json.loads(json.dumps(state)))
        self.assertEqual(state["castIds"], restored["castIds"])
        self.assertEqual(state["customPlayerCard"], restored["customPlayerCard"])
        projected = project_view(restored)
        self.assertNotIn("customPlayerCard", projected["snapshot"])
        self.assertTrue(projected["snapshot"]["player"]["isCustom"])
        player = next(c for c in projected["characters"] if c["isPlayerPerspective"])
        self.assertFalse(player["chatEnabled"])
        self.assertTrue(player["isCustom"])
        restarted = custom_snapshot(player_card_for(restored))
        self.assertEqual(restored["player"], restarted["player"])

    def test_missing_or_wrong_custom_identity_fails_closed_not_to_guest(self):
        state = custom_snapshot()
        invalid = deepcopy(state)
        invalid.pop("customPlayerCard")
        with self.assertRaisesRegex(ValueError, "资料缺失"):
            migrate_snapshot(invalid)
        invalid = deepcopy(state)
        invalid["customPlayerCard"]["id"] = f"custom-{uuid4()}"
        with self.assertRaisesRegex(ValueError, "身份不一致"):
            project_view(invalid)

    def test_legacy_snapshot_still_loads_without_custom_profile(self):
        state = create_snapshot("ENFP", "jiangmi")
        self.assertEqual("jiangmi", migrate_snapshot(state)["player"]["perspectiveCharacterId"])
        self.assertNotIn("customPlayerCard", project_view(state)["snapshot"])

    def test_every_day1_and_director_media_fallback_is_the_uploaded_identity(self):
        state = custom_snapshot()
        own_id = state["player"]["perspectiveCharacterId"]
        for node_id in DAY1_MEDIA_CONTRACT:
            state["nodeId"] = node_id
            media = day1_media_context(state)
            self.assertEqual(own_id, media["variantForCharacterId"])
            self.assertEqual("/api/custom-media/owner-opaque-photo", media["poster"])
            self.assertFalse(media["available"])
        for event in STORY_EVENTS:
            media = resolve_story_event_media(event, state, [state["castIds"][1]])
            # Existing reviewed NPC-only scenes are allowed; no such asset may
            # pretend the NPC is the uploaded player.
            if media.get("status") == "identity-safe-fallback":
                self.assertEqual(own_id, media["variantForCharacterId"])
                self.assertEqual("/api/custom-media/owner-opaque-photo", media["poster"])

    def test_candidate_video_is_not_runtime_until_explicitly_approved(self):
        card = custom_card()
        card["video"] = "/api/custom-media/owner-opaque-video"
        card["media"]["status"] = "generated-candidate"
        self.assertFalse(project_view(custom_snapshot(card))["mediaContext"]["available"])
        card["media"]["status"] = "approved-runtime"
        view = project_view(custom_snapshot(card))
        self.assertEqual(card["video"], view["mediaContext"]["src"])
        self.assertTrue(view["mediaContext"]["available"])

    def test_all_prompt_paths_receive_custom_identity_without_media_credentials(self):
        state = custom_snapshot()
        card = player_card_for(state)
        npc = CHARACTER_CARD_MAP[state["castIds"][1]]
        messages = [
            build_day1_script_messages(state),
            build_day1_node_messages(state, "introductions"),
            build_agent_messages(npc, state, "你好，很高兴认识你"),
            build_chat_opening_messages(npc, state),
            build_story_director_messages(state, eligible_story_events(state)),
        ]
        for bundle in messages:
            text = json.dumps(bundle, ensure_ascii=False)
            self.assertIn(card["names"]["primary"], text)
            self.assertIn(card["userProfile"]["preferences"], text)
            self.assertIn(card["userProfile"]["boundaries"], text)
            self.assertNotIn("/api/custom-media/", text)
        from backend.agent_prompt import _confirmed_public_facts
        public = _confirmed_public_facts(card)
        self.assertEqual({"age", "occupation", "publicPersona"}, set(public))
        self.assertNotIn("preferences", public)
        self.assertNotIn("mediaIdentity", runtime_character_card(card))

    def test_intro_fallbacks_and_no_shared_guest_script_cache(self):
        state = custom_snapshot()
        installed = install_day1_script(state, None)
        self.assertEqual(state["player"], installed["player"])
        self.assertIsNone(install_cached_day1_script(state))
        with character_scope(state):
            for option in state["scriptFlavor"]["nodes"]["introductions"]["choices"]:
                _validate_introduction_choice(state["player"]["perspectiveCharacterId"], option["id"], option["label"])

    def test_every_node_can_be_validated_with_a_custom_protagonist(self):
        for occupation, about in (("产品设计师", "喜欢散步"), ("职业暂未公开", "")):
            card = custom_card()
            card["sourceProfile"]["facts"].update(occupation=occupation, publicPersona=about)
            card["customIntroduction"] = f"大家好，我是云青，MBTI是ISTP。来这里想和大家慢慢认识。"
            state = custom_snapshot(card)
            for node_id, node in state["scriptFlavor"]["nodes"].items():
                with self.subTest(node=node_id, occupation=occupation):
                    result = validate_day1_node_script(state, node_id, node)
                    self.assertEqual(node["title"], result["title"])

    def test_choices_chat_memory_letter_complete_with_custom_player(self):
        state = custom_snapshot()
        for _ in range(5):
            view = project_view(state)
            state, _receipt = apply_choice(state, view["node"]["choices"][0]["id"])
        self.assertEqual("guided-chat", state["nodeId"])
        target_id = state["guidedTargetCharacterId"]
        npc = CHARACTER_CARD_MAP[target_id]
        state, _turn = commit_agent_turn(state, target_id, "你好，我是云青，很高兴认识你。", valid_turn(npc))
        self.assertIn("云青", state["echoMemories"][-1]["participantNames"])
        self.assertEqual("云青", state["conversationHistory"][-1]["turns"][-1]["playerCharacterName"])
        self.assertIn("云青", state["conversationHistory"][-1]["participantNames"])
        for _ in range(2):
            view = project_view(state)
            state, _receipt = apply_choice(state, view["node"]["choices"][0]["id"])
        self.assertEqual("anonymous-letter", state["nodeId"])
        option = project_view(state)["node"]["choices"][0]
        state, _receipt = apply_choice(state, option["id"], option["characterId"], custom_text="今天很高兴认识你，希望明天还能一起散步。")
        self.assertEqual("callback", state["nodeId"])
        self.assertIn("今天很高兴", state["heartMailbox"]["sent"][0]["body"])
        self.assertEqual("云青", project_view(state)["snapshot"]["player"]["displayName"])

    def test_custom_player_cannot_chat_with_themself(self):
        state = custom_snapshot()
        with self.assertRaisesRegex(ValueError, "自己私聊"):
            commit_agent_turn(state, state["player"]["perspectiveCharacterId"], "你好", {})
        contexts = available_chat_contexts(state)
        self.assertNotIn(state["player"]["perspectiveCharacterId"], [character["id"] for venue in contexts["venues"] for character in venue["characters"]])


class CustomPlayerIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_task_local_scope_never_leaks_to_another_user_or_library(self):
        first = custom_snapshot(custom_card(name="用户甲"))
        second = custom_snapshot(custom_card(name="用户乙"))

        async def read_while_other_task_runs(owned, other):
            own_id, other_id = owned["player"]["perspectiveCharacterId"], other["player"]["perspectiveCharacterId"]
            with character_scope(owned):
                await asyncio.sleep(0)
                self.assertEqual(owned["player"]["displayName"], CHARACTER_MAP[own_id]["name"])
                self.assertNotIn(other_id, CHARACTER_MAP)
                self.assertEqual(33, len(CHARACTER_MAP))
                self.assertEqual(owned["player"], migrate_snapshot(owned)["player"])
            self.assertNotIn(own_id, CHARACTER_MAP)

        await asyncio.gather(read_while_other_task_runs(first, second), read_while_other_task_runs(second, first))
        self.assertEqual(32, len(CHARACTER_MAP))


if __name__ == "__main__":
    unittest.main()
