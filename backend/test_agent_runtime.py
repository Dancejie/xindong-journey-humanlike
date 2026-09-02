from __future__ import annotations

import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from backend.app import (
    _agent_turn,
    _chat_opening,
    _generate_day1_node_script,
    _generate_day1_script,
    _story_director_turn,
)
from backend.agent_prompt import fallback_chat_opening
from backend.game_content import (
    CHARACTER_CARD_MAP,
    CHARACTER_MAP,
    active_cast_ids,
    build_fallback_script_flavor,
    create_snapshot,
)


def _runtime_turn(card: dict, dialogue: str, topic: str) -> dict:
    return {
        "dialogue": dialogue,
        "stageDirection": "他把手里的杯子放到一边，认真接住这句话",
        "attitude": "warm",
        "intentId": card["agentPolicy"]["allowedIntentIds"][0],
        "publicReason": "回应了当下的具体细节",
        "relationshipDelta": {axis: 0 for axis in card["agentPolicy"]["deltaBounds"]},
        "memory": {
            "kind": "episodic", "summary": topic, "interpretation": "这件事以后还可以继续了解",
            "salience": 55, "emotionalValence": 12,
        },
        "topicSummary": topic,
        "proposedEventId": None,
    }


class AgentRuntimeRewriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_protagonists_start_without_waiting_for_full_deepseek_script(self) -> None:
        fake_llm = AsyncMock(side_effect=AssertionError("start path must not call DeepSeek"))

        with (
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": "configured-for-test"}),
            patch("backend.app.install_cached_day1_script", return_value=None),
            patch("backend.app._llm_text", fake_llm),
        ):
            for card in CHARACTER_CARD_MAP.values():
                with self.subTest(character_id=card["id"]):
                    snapshot = create_snapshot(card["mbti"], card["id"])
                    result = await _generate_day1_script(snapshot)
                    self.assertEqual("fallback", result["scriptFlavor"]["source"])
        fake_llm.assert_not_awaited()

    async def test_dots_runtime_paths_receive_character_few_shots_and_provenance(self) -> None:
        snapshot = create_snapshot("ENFP", "jiangmi")
        target_id = next(character_id for character_id in active_cast_ids(snapshot) if character_id != "jiangmi")
        card = CHARACTER_CARD_MAP[target_id]

        snapshot["echoMemories"] = [{
            "characterId": target_id, "kind": "episodic", "summary": "两人在玄关聊过行李",
            "interpretation": "玩家愿意一起分担", "agentReply": "我来扶门，你先把箱子推进来。",
        }]
        turn = _runtime_turn(card, "刚才那只箱子确实难推。晚餐分工别客气，你挑一件，我补另一件。", "晚餐具体分工")
        turn_llm = AsyncMock(return_value=json.dumps(turn, ensure_ascii=False))
        dots_env = {"DOTS_API_KEY": "configured-for-test", "DOTS_MODEL": "dots-test-model"}
        with patch.dict(os.environ, dots_env, clear=False), patch("backend.app._llm_text", turn_llm):
            _, turn_generator = await _agent_turn(
                CHARACTER_MAP[target_id], snapshot, "刚才谢谢你扶门。", provider="dots",
            )
        turn_messages = turn_llm.await_args.args[0]
        self.assertEqual("dots", turn_llm.await_args.kwargs["provider"])
        self.assertEqual({"provider": "dots", "model": "dots-test-model"}, turn_generator)
        self.assertIn('"retrievedFewShotStructures"', turn_messages[1]["content"])
        self.assertIn(f'"characterId": "{target_id}"', turn_messages[1]["content"])
        self.assertIn('"retrievedPlayerStrategyFewShotStructures"', turn_messages[1]["content"])

        cold_snapshot = create_snapshot("ENFP", "jiangmi")
        opening_payload = fallback_chat_opening(card, cold_snapshot)
        opening_llm = AsyncMock(return_value=json.dumps(opening_payload, ensure_ascii=False))
        with (
            patch.dict(os.environ, dots_env, clear=False),
            patch("backend.app._llm_text", opening_llm),
        ):
            _, opening_generator = await _chat_opening(card, cold_snapshot, "dots")
        opening_messages = opening_llm.await_args.args[0]
        self.assertEqual("dots", opening_llm.await_args.kwargs["provider"])
        self.assertEqual({"provider": "dots", "model": "dots-test-model"}, opening_generator)
        opening_context = json.loads(opening_messages[1]["content"])["context"]
        self.assertEqual(target_id, opening_context["retrievedFewShotStructures"]["characterId"])
        self.assertEqual("jiangmi", opening_context["retrievedPlayerStrategyFewShotStructures"]["characterId"])

        node_snapshot = create_snapshot("ISTP", "qiaolan")
        node_id = "arrival-context"
        fallback_node = build_fallback_script_flavor("qiaolan", active_cast_ids(node_snapshot))["nodes"][node_id]
        node_llm = AsyncMock(return_value=json.dumps({"node": fallback_node}, ensure_ascii=False))
        with (
            patch.dict(os.environ, dots_env, clear=False),
            patch("backend.app._llm_text", node_llm),
        ):
            result = await _generate_day1_node_script(node_snapshot, node_id, "dots")
        self.assertIsNotNone(result)
        _, node_generator = result
        self.assertEqual({"provider": "dots", "model": "dots-test-model"}, node_generator)
        node_messages = node_llm.await_args.args[0]
        self.assertEqual("dots", node_llm.await_args.kwargs["provider"])
        node_context = json.loads(node_messages[1]["content"])["context"]
        self.assertEqual("qiaolan", node_context["retrievedFewShotStructures"]["characterId"])

    async def test_repeat_is_rewritten_locally_without_real_deepseek_call(self) -> None:
        snapshot = create_snapshot("ENFP", "jiangmi")
        target_id = next(
            character_id for character_id in active_cast_ids(snapshot)
            if character_id != "jiangmi" and CHARACTER_MAP[character_id]["gender"] == "男性"
        )
        card = CHARACTER_CARD_MAP[target_id]
        repeated = "刚才你说有点紧张，我也会紧张。要不要喝点什么？"
        snapshot["echoMemories"] = [
            {"characterId": target_id, "agentReply": repeated},
            {"characterId": target_id, "agentReply": "我把晚餐分工记下来了，不用再从头问一次。"},
        ]
        snapshot["agentConversations"][target_id] = {
            "turnCount": 2, "topicLedger": [{"topic": "刚进小屋为什么紧张"}],
        }
        first = _runtime_turn(card, repeated, "重复紧张话题")
        second = _runtime_turn(
            card,
            "我刚才也认错了两个人的名字，幸好你先笑了，不然我还得装镇定。晚餐分工我负责收尾，你挑想做的那一段。",
            "用认错名字化解紧张",
        )
        fake_llm = AsyncMock(side_effect=[
            json.dumps(first, ensure_ascii=False), json.dumps(second, ensure_ascii=False),
        ])
        with patch("backend.app._llm_text", fake_llm):
            result, generator = await _agent_turn(CHARACTER_MAP[target_id], snapshot, "其实我现在还是有点紧张。")

        self.assertEqual(second["dialogue"], result["dialogue"])
        self.assertEqual("deepseek", generator["provider"])
        self.assertEqual(2, fake_llm.await_count)

    async def test_story_director_freezes_dots_provider_and_reports_provenance(self) -> None:
        fake_llm = AsyncMock(return_value="{}")
        validated = {"decision": "wait", "proposedEventId": None}
        with (
            patch.dict(os.environ, {"DOTS_API_KEY": "configured", "DOTS_MODEL": "dots-director-test"}, clear=False),
            patch("backend.app.build_story_director_messages", return_value=[{"role": "user", "content": "test"}]),
            patch("backend.app.validate_story_director_output", return_value=validated),
            patch("backend.app._llm_text", fake_llm),
        ):
            proposal, generator = await _story_director_turn({}, [], "dots")

        self.assertEqual(validated, proposal)
        self.assertEqual({"provider": "dots", "model": "dots-director-test"}, generator)
        self.assertEqual("dots", fake_llm.await_args.kwargs["provider"])


if __name__ == "__main__":
    unittest.main()
