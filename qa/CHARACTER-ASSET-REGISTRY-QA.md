# Character Asset Registry QA

- Date: 2026-08-27
- Verdict: `CHARACTER_ASSET_REGISTRY_PASS`
- Characters: 16
- Registry assets: 159
  - Static identity portraits: 16
  - Dynamic character portraits: 16
  - Existing event/runtime routes: 127
- Validation failures: 0
- Specialized tests: 5 passed

Commands:

```bash
python3 scripts/build_character_asset_registry.py
python3 scripts/validate_character_asset_registry.py
python3 scripts/test_character_asset_registry.py -v
```

The registry covers all 143 entries in `media/runtime-media-manifest.json` plus
the 16 static identity anchors that the historical runtime manifest did not
index. It validates file existence, SHA-256, canonical-name uniqueness,
character-card MBTI/gender binding, single-person identity scope, runtime route
lead binding, dimensions, duration, audio metadata, and cross-identity byte
reuse.

Proof boundary: this is a structural and declared-identity audit. It does not
prove that a generated face visually matches its reference anchor. That still
requires human frame review. Rights remain `pending` for 81 R6-planned assets
and `unknown-not-reviewed` for 78 historical/static assets; runtime approval is
not a commercial/public-release rights grant.
