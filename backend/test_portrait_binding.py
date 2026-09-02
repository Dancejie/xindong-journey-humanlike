from __future__ import annotations

import unittest
from pathlib import Path

from game_content import CHARACTERS, RUNTIME_ASSET_MAP


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MEDIA = ROOT / "frontend" / "public"
COUNTERPART_IDS = {
    "luyao", "yecheng", "tangli", "wenxu",
    "hechuan", "peiran", "lichuan", "qiaolan",
}
R9_ROSTER_IDS = {
    "shaozheng", "qince", "jiheng", "xiache", "zhouyan", "ningzhi", "xuhang", "gutang",
    "yanxu", "jianning", "luozheng", "chengqing", "xiemu", "yaoyin", "hanxi", "luoxing",
}
R9B_REPAIR_SOURCE_IDS = {
    "shaozheng": "shaozheng--entj--male--001b--dynamic-portrait-no-text",
    "qince": "qince--entj--female--001b--dynamic-portrait-no-text",
}
R9B_TECHNICAL_QA_PATH = (
    "media/production/full-mbti-r9/repair-entj-r9b/technical-qa.normalized.r9b.json"
)
R9B_VISUAL_QA_PATH = (
    "media/production/full-mbti-r9/repair-entj-r9b/visual-audio-qa-report-r9b.md"
)
R9B_QA_ALLOWLIST_PATH = (
    "media/production/full-mbti-r9/repair-entj-r9b/visual-audio-qa-allowlist.r9b.json"
)


class PortraitBindingTests(unittest.TestCase):
    def test_all_selection_cards_have_an_honest_static_visual(self):
        self.assertEqual(32, len(CHARACTERS))
        for character in CHARACTERS:
            character_id = character["id"]
            with self.subTest(character_id=character_id):
                expected = f"/media/portraits/{character_id}.jpg"
                self.assertEqual("identity-portrait", character["portraitKind"])
                self.assertEqual(expected, character["portrait"])
                self.assertTrue((PUBLIC_MEDIA / expected.lstrip("/")).is_file())

    def test_new_counterparts_keep_same_identity_dynamic_portraits(self):
        for character_id in COUNTERPART_IDS:
            asset = RUNTIME_ASSET_MAP[f"CHAR-{character_id}-portrait"]
            expected = f"/media/video/CHAR-{character_id}-portrait.mp4"
            with self.subTest(character_id=character_id):
                self.assertEqual("approved-runtime", asset["status"])
                self.assertEqual([character_id], asset["identityCast"])
                self.assertEqual(expected, asset["path"])
                self.assertTrue((PUBLIC_MEDIA / expected.lstrip("/")).is_file())
                projected = next(item for item in CHARACTERS if item["id"] == character_id)
                self.assertEqual(expected, projected["video"])

    def test_reviewed_r9_and_r9b_dynamic_portraits_are_exact(self):
        for character_id in R9_ROSTER_IDS:
            asset = RUNTIME_ASSET_MAP[f"CHAR-{character_id}-portrait"]
            expected = f"/media/video/CHAR-{character_id}-portrait.mp4"
            with self.subTest(character_id=character_id):
                self.assertEqual("approved-runtime", asset["status"])
                self.assertEqual([character_id], asset["identityCast"])
                self.assertEqual(expected, asset["path"])
                self.assertTrue((PUBLIC_MEDIA / expected.lstrip("/")).is_file())
                projected = next(item for item in CHARACTERS if item["id"] == character_id)
                self.assertEqual("ready", projected["mediaStatus"])
                self.assertEqual(expected, projected["video"])

        for character_id, source_id in R9B_REPAIR_SOURCE_IDS.items():
            with self.subTest(character_id=character_id):
                asset = RUNTIME_ASSET_MAP[f"CHAR-{character_id}-portrait"]
                self.assertEqual(source_id, asset["sourceId"])
                self.assertEqual(R9B_TECHNICAL_QA_PATH, asset["technicalQaEvidence"])
                self.assertEqual(R9B_VISUAL_QA_PATH, asset["visualQaEvidence"])
                self.assertEqual(R9B_QA_ALLOWLIST_PATH, asset["qaEvidence"])
                self.assertTrue((ROOT / asset["technicalQaEvidence"]).is_file())
                self.assertTrue((ROOT / asset["visualQaEvidence"]).is_file())
                self.assertTrue((ROOT / asset["qaEvidence"]).is_file())


if __name__ == "__main__":
    unittest.main()
