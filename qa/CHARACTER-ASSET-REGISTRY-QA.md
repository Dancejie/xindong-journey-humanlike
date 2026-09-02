# Character Asset Registry QA

- Date: 2026-09-02
- Verdict: `CHARACTER_ASSET_REGISTRY_PASS`
- Character directory rows: 32
  - Runtime static + dynamic identity-media covered: 32
  - Runtime static-only because reviewed dynamic candidate is held: 0
  - Planned/blocked with no identity media: 0
- Registry assets: 197
  - Static identity portraits: 32
  - Dynamic character portraits: 32
  - Existing event/runtime routes: 133
- Validation failures: 0
- Specialized tests: 7 passed

Commands:

```bash
python3 scripts/build_character_asset_registry.py
python3 scripts/validate_character_asset_registry.py
python3 scripts/test_character_asset_registry.py -v
```

The registry is a 32-card directory: exactly one male and one female card for
each of the 16 MBTI types. It covers all 165 entries in
`media/runtime-media-manifest.json` plus the 32 static identity anchors that the
runtime video manifest does not index. Every character now has one exact static
portrait and one approved dynamic portrait. The old R9 `qince` and `shaozheng`
candidates remain held as historical evidence; only the separately authorized,
new-source R9B derivatives were promoted after technical and human QA.

Validation covers file existence, SHA-256, canonical-name uniqueness,
character-card MBTI/gender binding, single-person identity scope, runtime route
lead binding, dimensions, duration, audio metadata, and cross-identity byte
reuse. R9 also validates every top-level source-manifest path/SHA binding and
the source-code evidence locators declared for already-running legacy assets.

R9 added `E01-arrival-reveal` and `E01-anonymous-letter`, which were already
referenced by runtime code but missing from both ledgers. Both are technically
verified and runtime-integrated, but remain `provisional`: their current images
do not fully prove the associated node copy and their rights are unreviewed.

Proof boundary: `CHARACTER_ASSET_REGISTRY_PASS` means the ledger and its explicit
coverage states are structurally consistent. The 18 R9 assets and 2 R9B repair
assets also passed retained human identity/continuity review, but this registry
validator itself does not perform semantic face recognition. Runtime approval
is not deployment or a commercial/public-release rights grant; historical and
generated assets retain their separately recorded rights status.
