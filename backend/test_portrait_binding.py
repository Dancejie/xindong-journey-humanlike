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


class PortraitBindingTests(unittest.TestCase):
    def test_all_selection_cards_use_identity_specific_static_portraits(self):
        self.assertEqual(16, len(CHARACTERS))
        for character in CHARACTERS:
            character_id = character["id"]
            expected = f"/media/portraits/{character_id}.jpg"
            with self.subTest(character_id=character_id):
                self.assertEqual(expected, character["portrait"])
                self.assertNotIn("portraits-placeholders", character["portrait"])
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


if __name__ == "__main__":
    unittest.main()
