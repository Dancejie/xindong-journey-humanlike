#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from itertools import combinations
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_character_cards_v3.py"
SPEC = importlib.util.spec_from_file_location("character_card_builder", BUILDER_PATH)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class CharacterCardDistinctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package = json.loads((ROOT / "content" / "character_cards.v3.json").read_text(encoding="utf-8"))
        cls.sources = json.loads((ROOT / "content" / "research_sources.v3.json").read_text(encoding="utf-8"))

    def test_current_thirty_two_cards_pass_exact_and_near_duplicate_gates(self) -> None:
        BUILDER.validate_built_r9(deepcopy(self.package), deepcopy(self.sources))
        maximum_same_type = (0.0, 0.0)
        maximum_global = (0.0, 0.0)
        for first, second in combinations(self.package["cards"], 2):
            score = BUILDER.distinction_similarity(first, second)
            if first["mbti"] == second["mbti"]:
                maximum_same_type = max(maximum_same_type, score)
            else:
                maximum_global = max(maximum_global, score)
        self.assertLess(maximum_same_type[0], BUILDER.SAME_TYPE_MAX_SEQUENCE_RATIO)
        self.assertLess(maximum_same_type[1], BUILDER.SAME_TYPE_MAX_TRIGRAM_JACCARD)
        self.assertLess(maximum_global[0], BUILDER.GLOBAL_MAX_SEQUENCE_RATIO)
        self.assertLess(maximum_global[1], BUILDER.GLOBAL_MAX_TRIGRAM_JACCARD)

    def test_near_reskin_is_rejected_even_when_exact_fields_are_slightly_changed(self) -> None:
        mutated = deepcopy(self.package)
        source = next(card for card in mutated["cards"] if card["id"] == "shenmo")
        target = next(card for card in mutated["cards"] if card["id"] == "luyao")
        target["tagline"] = source["tagline"] + "另一种"
        target["identity"]["canonicalRoles"][-1] = source["identity"]["canonicalRoles"][-1] + "协作"
        target["cognitiveStyle"] = deepcopy(source["cognitiveStyle"])
        target["cognitiveStyle"]["inputFilter"] += "并留一次复核"
        target["cognitiveStyle"]["repairMove"] += "再交回选择"
        target["voice"] = deepcopy(source["voice"])
        target["interactionStrategies"] = deepcopy(source["interactionStrategies"])
        strategy_key = next(iter(target["interactionStrategies"]))
        target["interactionStrategies"][strategy_key] += "并确认一次"
        target["memoryPolicy"]["remember"] = deepcopy(source["memoryPolicy"]["remember"])
        target["memoryPolicy"]["remember"].append("一项补充记录")
        target["reactionMatrix"] = deepcopy(source["reactionMatrix"])
        target["reactionMatrix"]["supportive"]["speechMove"] += "再问一句"
        target["dialoguePolicy"]["distinctiveVoiceGate"] = "仍看似独立，但核心是近似换皮"

        with self.assertRaisesRegex(ValueError, "near-duplicate character cores"):
            BUILDER.validate_built_r9(mutated, deepcopy(self.sources))


if __name__ == "__main__":
    unittest.main()
