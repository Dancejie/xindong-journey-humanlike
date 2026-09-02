#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "media" / "character-asset-registry.v1.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate_character_asset_registry.py"
R9B_REPAIR_SOURCE_IDS = {
    "shaozheng": "shaozheng--entj--male--001b--dynamic-portrait-no-text",
    "qince": "qince--entj--female--001b--dynamic-portrait-no-text",
}
SPEC = importlib.util.spec_from_file_location("character_asset_registry_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class CharacterAssetRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_committed_registry_passes_full_validation(self) -> None:
        self.assertEqual([], VALIDATOR.validate_registry(self.registry, root=ROOT))

    def test_identity_media_is_complete_for_all_32_characters(self) -> None:
        assets = self.registry["assets"]
        characters = {item["characterId"] for item in self.registry["characters"]}
        static = {item["characterId"] for item in assets if item["mediaType"] == "image" and item["sequence"] == "000"}
        dynamic = {item["characterId"] for item in assets if item["mediaType"] == "video" and item["sequence"] == "001"}
        covered = {
            item["characterId"] for item in self.registry["characters"]
            if item["mediaCoverage"]["status"] == "runtime-identity-covered"
        }
        planned = {
            item["characterId"] for item in self.registry["characters"]
            if item["mediaCoverage"]["status"] == "planned-no-runtime-identity-media"
        }
        static_only = {
            item["characterId"] for item in self.registry["characters"]
            if item["mediaCoverage"]["status"] == "runtime-static-only-held-dynamic"
        }
        self.assertEqual(covered | static_only, static)
        self.assertEqual(covered, dynamic)
        self.assertEqual(characters, covered | static_only | planned)
        self.assertEqual(32, len(covered))
        self.assertEqual(set(), static_only)
        self.assertEqual(set(), planned)
        self.assertEqual(set(), covered & static_only)
        self.assertEqual(set(), covered & planned)
        self.assertEqual(set(), static_only & planned)

    def test_r9b_registry_preserves_repair_source_ids(self) -> None:
        assets = {
            item.get("legacyAssetId"): item
            for item in self.registry["assets"]
            if item.get("legacyAssetId")
        }
        for character_id, source_id in R9B_REPAIR_SOURCE_IDS.items():
            runtime_id = f"CHAR-{character_id}-portrait"
            with self.subTest(character_id=character_id):
                asset = assets[runtime_id]
                self.assertEqual(source_id, asset["source"]["sourceId"])
                self.assertEqual("runtime-integrated", asset["runtimeIntegrationStatus"])

    def test_mbti_drift_is_rejected(self) -> None:
        mutated = deepcopy(self.registry)
        lichuan = next(item for item in mutated["assets"] if item.get("characterId") == "lichuan")
        lichuan["mbti"] = "ESTP"
        failures = VALIDATOR.validate_registry(mutated, root=ROOT, verify_hashes=False)
        self.assertTrue(any("primary character metadata mismatch" in failure for failure in failures))

    def test_cross_character_byte_reuse_is_rejected(self) -> None:
        mutated = deepcopy(self.registry)
        chengye = next(
            item for item in mutated["assets"]
            if item.get("characterId") == "chengye" and item.get("sequence") == "001"
        )
        lichuan = next(
            item for item in mutated["assets"]
            if item.get("characterId") == "lichuan" and item.get("sequence") == "001"
        )
        lichuan["sha256"] = chengye["sha256"]
        failures = VALIDATOR.validate_registry(mutated, root=ROOT, verify_hashes=False)
        self.assertTrue(any("cross-identity SHA reuse" in failure for failure in failures))

    def test_duplicate_canonical_filename_is_rejected(self) -> None:
        mutated = deepcopy(self.registry)
        mutated["assets"][1]["canonicalFilename"] = mutated["assets"][0]["canonicalFilename"]
        failures = VALIDATOR.validate_registry(mutated, root=ROOT, verify_hashes=False)
        self.assertTrue(any("duplicate canonicalFilename" in failure for failure in failures))

    def test_character_cards_source_sha_drift_is_rejected(self) -> None:
        mutated = deepcopy(self.registry)
        mutated["sourceManifests"]["characterCards"]["sha256"] = "0" * 64
        failures = VALIDATOR.validate_registry(mutated, root=ROOT)
        self.assertTrue(any("source manifest SHA mismatch: characterCards" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
