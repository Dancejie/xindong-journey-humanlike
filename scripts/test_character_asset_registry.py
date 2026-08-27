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

    def test_all_sixteen_characters_have_static_and_dynamic_identity_assets(self) -> None:
        assets = self.registry["assets"]
        characters = {item["characterId"] for item in self.registry["characters"]}
        static = {item["characterId"] for item in assets if item["mediaType"] == "image" and item["sequence"] == "000"}
        dynamic = {item["characterId"] for item in assets if item["mediaType"] == "video" and item["sequence"] == "001"}
        self.assertEqual(characters, static)
        self.assertEqual(characters, dynamic)

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


if __name__ == "__main__":
    unittest.main()
