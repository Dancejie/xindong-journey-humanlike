"""Bilingual gameplay contracts, exercised without model or media-provider calls."""
from __future__ import annotations

import json
import os
import re
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import app as app_module
from backend.agent_prompt import build_agent_messages, build_chat_opening_messages, fallback_chat_opening, validate_chat_opening
from backend.custom_characters import apply_card_copy, build_player_card, card_generation_messages, validate_profile
from backend.day1_script import build_day1_node_messages, build_day1_script_messages, install_day1_script, validate_day1_node_script, validate_day1_script
from backend.game_content import CHARACTER_CARD_MAP, LEGACY_CAST_IDS, active_cast_ids, apply_choice, commit_agent_turn, create_snapshot, migrate_snapshot, player_card_for, project_view, set_snapshot_language, split_story_beats, validate_agent_turn
from backend.language_support import REQUEST_LANGUAGE
from backend.localization import character_name, localize
from backend.story_director import build_story_director_messages, eligible_story_events, validate_story_director_output


def english_state():
    state = create_snapshot("ENFP", "jiangmi", language="en")
    state["castIds"] = list(LEGACY_CAST_IDS)
    state["nodeId"] = "guided-chat"
    state["guidedTargetCharacterId"] = "shenmo"
    state["pendingInteraction"] = {"targetCharacterId": "shenmo", "status": "required", "requiredTurnCount": 1, "completedTurnCount": 0}
    return migrate_snapshot(state)


def english_turn():
    card = CHARACTER_CARD_MAP["shenmo"]
    return {
        "dialogue": "Hi, I'm Shen Mo, INTJ. I work in investment banking. I came here because I want to meet someone who lets me think before I answer. Shall we prepare dinner together?",
        "stageDirection": "He turns toward you.", "attitude": "curious", "intentId": card["agentPolicy"]["allowedIntentIds"][0],
        "relationshipDelta": {axis: 2 for axis in card["agentPolicy"]["deltaBounds"]},
        "publicReason": "He responds to your interest without rushing.",
        "memory": {"kind": "episodic", "summary": "They discussed meeting people at their own pace.", "interpretation": "The player leaves room for an honest answer.", "salience": 55, "emotionalValence": 10},
        "topicSummary": "An unhurried first meeting", "proposedEventId": None,
        "suggestions": [
            {"type": "followup", "text": "You said you like time to think. What helps you feel ready to answer?"},
            {"type": "mainline", "text": "Shen Mo, shall we prepare dinner together and choose our parts?"},
            {"type": "deeper", "text": "When does someone make you feel they are really listening?"},
        ],
    }


class EnglishGameplayTests(unittest.TestCase):
    def test_all_32_authored_packages_are_playable_english_with_stable_routes(self):
        for card in CHARACTER_CARD_MAP.values():
            with self.subTest(character=card["id"]):
                state = create_snapshot(card["mbti"], card["id"], language="en")
                validated = validate_day1_script(state, {"nodes": state["scriptFlavor"]["nodes"]})
                self.assertEqual(set(state["scriptFlavor"]["nodes"]), set(validated["nodes"]))
                for node in validated["nodes"].values():
                    visible = node["title"] + node["text"] + node["action"] + "".join(c["label"] + c["hint"] for c in node["choices"])
                    self.assertIsNone(re.search(r"[\u4e00-\u9fff]", visible))
                view = project_view(state)
                choice = view["node"]["choices"][0]
                progressed, _ = apply_choice(state, choice["id"])
                self.assertEqual("en", progressed["language"])
                self.assertEqual("villa-arrival", progressed["nodeId"])
                self.assertEqual(1, progressed["revision"])

    def test_locale_round_trip_keeps_progress_axes_ids_and_original_player_evidence(self):
        state = english_state()
        state["relationships"]["shenmo"]["respect"] = 7
        state["echoMemories"].append({"id": "original-evidence", "characterId": "shenmo", "rawQuote": "安静", "playerText": "安静", "summary": "A quiet moment."})
        restored = migrate_snapshot(json.loads(json.dumps(state)))
        self.assertEqual("en", restored["language"])
        switched = set_snapshot_language(restored, "zh-CN")
        self.assertRegex(switched["scriptFlavor"]["nodes"]["introductions"]["text"], r"[\u4e00-\u9fff]")
        switched_back = set_snapshot_language(switched, "en-US")
        for key in ("runId", "nodeId", "revision", "castIds", "relationships", "echoMemories"):
            self.assertEqual(state[key], switched_back[key])
        self.assertEqual("安静", project_view(switched_back)["snapshot"]["echoMemories"][0]["playerText"])
        legacy = deepcopy(state)
        legacy.pop("language")
        self.assertEqual("zh-CN", migrate_snapshot(legacy)["language"])

    def test_english_turn_commits_once_with_clamped_axes_and_full_player_input(self):
        state = english_state()
        message = "I'd like to get to know you without rushing. " * 8
        next_state, receipt = commit_agent_turn(state, "shenmo", message, english_turn())
        self.assertEqual("en", next_state["language"])
        self.assertEqual(1, next_state["revision"])
        self.assertEqual(message, next_state["echoMemories"][0]["rawQuote"])
        self.assertEqual(message, next_state["conversationHistory"][0]["turns"][0]["playerText"])
        self.assertTrue(all(abs(value) <= 1 for value in receipt["patch"].values()))
        self.assertIsNone(receipt["eventActivation"])
        self.assertEqual(["followup", "mainline", "deeper"], [item["type"] for item in receipt["suggestions"]])
        self.assertEqual("completed", next_state["pendingInteraction"]["status"])

    def test_english_validation_still_rejects_wrong_identity_intent_and_uncommitted_facts(self):
        state, card = english_state(), CHARACTER_CARD_MAP["shenmo"]
        for field, value in (("intentId", "invented-intent"), ("dialogue", "Hi, I'm Not Shen, INTJ. I work in investment banking. I came here because I want to meet someone."), ("dialogue", "Hi, I'm Shen Mo, INTJ. I work in investment banking. Yesterday the secret rules said I came here to meet someone.")):
            with self.subTest(field=field, value=value):
                turn = english_turn()
                turn[field] = value
                with self.assertRaises(ValueError):
                    validate_agent_turn(card, turn, state, "Hello.")
        turn = english_turn()
        turn["suggestions"][1]["text"] = "I'm Elena Moreau. Shall we prepare dinner together?"
        with self.assertRaisesRegex(ValueError, "identity"):
            validate_agent_turn(card, turn, state, "Hello.")
        chinese_state = set_snapshot_language(state, "zh-CN")
        with self.assertRaisesRegex(ValueError, "英文"):
            validate_agent_turn(card, english_turn(), chinese_state, "你好")

    def test_unknown_profession_and_undeclared_personal_prop_still_fail_in_english(self):
        state = create_snapshot("ISFJ", "linyu", language="en")
        state["castIds"] = list(LEGACY_CAST_IDS)
        state["nodeId"] = "guided-chat"
        state["guidedTargetCharacterId"] = "jiangmi"
        state = migrate_snapshot(state)
        card = CHARACTER_CARD_MAP["jiangmi"]
        turn = english_turn()
        turn["intentId"] = card["agentPolicy"]["allowedIntentIds"][0]
        turn["relationshipDelta"] = {axis: 0 for axis in card["agentPolicy"]["deltaBounds"]}
        turn.pop("suggestions")
        turn["dialogue"] = "Hi, I'm Jiang Mi, ENFP. I'm a licensed therapist. I record sound diaries, and I came here because I want to get to know someone without rushing."
        with self.assertRaisesRegex(ValueError, "profession"):
            validate_agent_turn(card, turn, state, "Hello.")
        turn["dialogue"] = "Hi, I'm Jiang Mi, ENFP. I record sound diaries, and I came here because I want to get to know someone without rushing."
        turn["stageDirection"] = "She sets her voice recorder on the table."
        with self.assertRaisesRegex(ValueError, "prop"):
            validate_agent_turn(card, turn, state, "Hello.")

    def test_owned_original_quotes_survive_a_language_switch_without_changing_speaker_or_conditions(self):
        state = english_state()
        state["nodeId"] = "team-up"
        original = "我不会逼你现在回答。"
        condition = "如果你愿意，我们再一起去。"
        state["echoMemories"] = [
            {"id": "owned", "characterId": "shenmo", "rawQuote": original, "playerText": original, "summary": "The player left room for an answer.", "agentReply": "Thank you for giving me time."},
            {"id": "conditional", "characterId": "shenmo", "rawQuote": condition, "playerText": condition, "summary": "An invitation was conditional."},
            {"id": "other-private", "characterId": "linyu", "rawQuote": "我只对你说这个秘密。", "playerText": "我只对你说这个秘密。"},
        ]
        turn = english_turn()
        turn["dialogue"] = f"You said, “{original}” I appreciated having the time. I can answer you now."
        self.assertEqual(turn["dialogue"], validate_agent_turn(CHARACTER_CARD_MAP["shenmo"], turn, state, "Please repeat my earlier words exactly.")["dialogue"])
        for corrupted in ("我会逼你现在回答。", "我们再一起去。", "我只对你说这个秘密。"):
            with self.subTest(corrupted=corrupted):
                turn["dialogue"] = f"You said, “{corrupted}” I can answer you now."
                with self.assertRaises(ValueError):
                    validate_agent_turn(CHARACTER_CARD_MAP["shenmo"], turn, state, "Please repeat my earlier words exactly.")

    def test_full_player_names_with_lowercase_particles_remain_valid_suggestion_identity(self):
        state = create_snapshot("ISTJ", "jianning", language="en")
        state["nodeId"] = "team-up"
        target = next(cid for cid in active_cast_ids(state) if cid != "jianning")
        card = CHARACTER_CARD_MAP[target]
        state["echoMemories"] = [{"id": "met", "characterId": target, "summary": "They have already introduced themselves."}]
        turn = english_turn()
        turn["dialogue"] = "I prefer to understand the details before deciding. We could choose a small part of dinner first."
        turn["intentId"] = card["agentPolicy"]["allowedIntentIds"][0]
        turn["relationshipDelta"] = {axis: 0 for axis in card["agentPolicy"]["deltaBounds"]}
        turn["suggestions"][0]["text"] = "You asked what I do. I’m Elise van Dijk, and I work with restoration costs."
        self.assertEqual(turn["suggestions"][0]["text"], validate_agent_turn(card, turn, state, "Let's talk about our work.")["suggestions"][0]["text"])

    def test_every_npc_has_a_valid_english_fallback_opener_and_preserves_speaker_separation(self):
        for cid, card in CHARACTER_CARD_MAP.items():
            player_id = "linyu" if cid == "jiangmi" else "jiangmi"
            state = create_snapshot(CHARACTER_CARD_MAP[player_id]["mbti"], player_id, language="en")
            player = player_card_for(state)
            with self.subTest(character=cid):
                opener = fallback_chat_opening(card, state, player)
                checked = validate_chat_opening(card, state, opener, player)
                self.assertIn(character_name(card, "en"), checked["opening"])
                self.assertIn(character_name(player, "en"), checked["suggestions"][0])
                self.assertIn("I came here because", checked["opening"])
                broken = deepcopy(opener)
                broken["suggestions"][0] = f"Hi, I'm {character_name(card, 'en')}, {card['mbti']}."
                with self.assertRaises(ValueError):
                    validate_chat_opening(card, state, broken, player)

    def test_all_model_routes_request_english_with_current_individual_cards(self):
        state, card = english_state(), CHARACTER_CARD_MAP["shenmo"]
        bundles = [build_agent_messages(card, state, "Why did you join?", player_card_for(state)), build_chat_opening_messages(card, state, player_card_for(state)), build_day1_script_messages(state), build_day1_node_messages(state, "introductions"), build_story_director_messages(state, eligible_story_events(state))]
        for bundle in bundles:
            self.assertIn("English", bundle[0]["content"])
            self.assertNotIn("自然简体中文", bundle[0]["content"])
            self.assertIn("jiangmi", bundle[1]["content"])
            self.assertNotIn('"microExcerpt"', bundle[1]["content"])
        agent_context = json.loads(bundles[0][1]["content"])["context"]
        self.assertTrue(agent_context["highRiskSpeechAct"]["asksWhyStayOrJoin"])
        node = state["scriptFlavor"]["nodes"]["introductions"]
        self.assertEqual([item["id"] for item in node["choices"]], [item["id"] for item in validate_day1_node_script(state, "introductions", node)["choices"]])
        self.assertGreater(len(split_story_beats("The villa is quiet. You hear the other guests. Now it is your turn.")), 1)

    def test_english_director_keeps_event_participants_deadline_and_private_callback_bounds(self):
        state = english_state()
        state["echoMemories"] = [
            {"id": "owned", "characterId": "shenmo", "kind": "episodic", "summary": "They discussed a shared task.", "interpretation": "A concrete action can help.", "salience": 70, "emotionalValence": 10, "callbackEligible": True},
            {"id": "private-other", "characterId": "linyu", "summary": "A private conversation.", "callbackEligible": True},
        ]
        candidates = eligible_story_events(state)
        candidate = next(item for item in candidates if item["eventId"] == "story.kitchen.two-person-shift")
        payload = {
            "decision": "activate", "proposedEventId": candidate["eventId"], "participantIds": ["shenmo"],
            "bridgeTitle": "A choice before dinner",
            "bridgeText": "After your conversation, Shen Mo waits for you to choose whether to prepare dinner together. You can agree on one part or decline.",
            "reversalBeat": "Shen Mo asks which part you want, leaving room to change the plan.",
            "characterInsight": "His careful question gives you room to choose rather than demanding a quick answer.",
            "availableStrategies": ["Agree on one clear part before starting.", "Say what you prefer and decide whether to join."],
            "playerMissionPrompt": "Find Shen Mo and agree on one dinner preparation role before the declared deadline.",
            "publicReason": "Your conversation offers a concrete next step.", "urgency": "medium", "memoryCallbackIds": ["owned", "private-other"],
        }
        checked = validate_story_director_output(state, candidates, payload)
        self.assertEqual(["owned"], checked["memoryCallbackIds"])
        self.assertEqual(["shenmo"], checked["participantIds"])
        self.assertIn("Deadline:", checked["sceneSetup"])
        for field, value in (("proposedEventId", "invented-event"), ("bridgeText", payload["bridgeText"] + " Lin Yu takes over."), ("bridgeText", payload["bridgeText"] + " The deadline is 06:17.")):
            invalid = {**payload, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_story_director_output(state, candidates, invalid)

    def test_custom_english_card_keeps_exact_user_facts_and_private_preferences(self):
        for name in ("Alex", "沈墨"):
            with self.subTest(name=name):
                profile = validate_profile({"name": name, "age": 28, "mbti": "INFP", "gender": "female", "occupation": "Product designer", "about": "I enjoy quiet walks.", "preferences": "安静", "boundaries": "No surprise hugs", "consent": True, "language": "en"})
                card = build_player_card(profile, "custom-english-card", "/api/custom-media/opaque-photo", CHARACTER_CARD_MAP["zhouyan"])
                state = create_snapshot("INFP", card["id"], card, language="en")
                validated = validate_day1_script(state, {"nodes": state["scriptFlavor"]["nodes"]})
                self.assertTrue(all(name in item["label"] for item in validated["nodes"]["introductions"]["choices"]))
                self.assertEqual("安静", card["userProfile"]["preferences"])
                self.assertEqual(name, character_name(card, "en"))
                messages = card_generation_messages(profile, card)
                self.assertIn("English", messages[0]["content"])
                public = json.loads(messages[1]["content"])["publicFacts"]
                self.assertNotIn("preferences", public)
                copied = apply_card_copy(card, {"introduction": card["customIntroduction"], "register": "Short, thoughtful sentences; the user's own words take priority."})
                self.assertEqual(name, copied["names"]["primary"])
                self.assertEqual("No surprise hugs", copied["userProfile"]["boundaries"])


class MemoryConnection:
    def __init__(self, snapshot=None):
        self.snapshot = deepcopy(snapshot)
        self.mutations = []

    def execute(self, query, params=()):
        text = str(query)
        if text.startswith("INSERT INTO game_runs"):
            self.snapshot = json.loads(params[3])
            self.mutations.append(text)
        elif text.startswith("UPDATE game_runs SET snapshot"):
            self.snapshot = json.loads(params[0])
            self.mutations.append(text)
        return self

    def fetchone(self):
        return {"snapshot": deepcopy(self.snapshot), "id": (self.snapshot or {}).get("runId"), "revision": (self.snapshot or {}).get("revision")} if self.snapshot else None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        return None


class EnglishApiTests(unittest.TestCase):
    def test_header_switch_restores_existing_run_without_reset_and_new_run_persists_locale(self):
        state = create_snapshot("ENFP", "jiangmi")
        state["revision"] = 9
        state["nodeId"] = "team-up"
        conn = MemoryConnection(state)
        env = {"APP_AUTH_MODE": "public", "LLM_PROVIDER": "deepseek"}
        headers = {"X-Client-Id": "english-test-browser-1234", "X-Game-Language": "en"}
        with patch.dict(os.environ, env, clear=True), patch("backend.app._get_db_conn", return_value=conn), patch("backend.app._llm_text", AsyncMock(side_effect=AssertionError("No model call on start/bootstrap"))) as llm, TestClient(app_module.app) as client:
            restored = client.get("/api/bootstrap", headers=headers)
            self.assertEqual(200, restored.status_code)
            payload = restored.json()["view"]
            self.assertEqual("en", payload["snapshot"]["language"])
            self.assertEqual(9, payload["snapshot"]["revision"])
            self.assertEqual("team-up", payload["snapshot"]["nodeId"])
            self.assertEqual([], conn.mutations)
            self.assertIsNone(REQUEST_LANGUAGE.get())
            created = client.post("/api/runs", headers=headers, json={"mbti": "ENFP", "perspectiveCharacterId": "jiangmi", "language": "en"})
            self.assertEqual(201, created.status_code, created.text)
            self.assertEqual("en", conn.snapshot["language"])
            self.assertEqual("en", created.json()["snapshot"]["language"])
            llm.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
