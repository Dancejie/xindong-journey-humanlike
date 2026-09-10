# External generation budget policy

Effective 2026-08-25 for this project and its future media batches:

- Reuse an existing generated asset whenever it already satisfies the event, identity, audio, framing and rights contract.
- Every manifest must report the project's cumulative external-generation spend before the batch, the incremental estimate for the batch, and the projected cumulative total.
- **CNY 200 is the manual-review threshold.** If either the batch estimate or projected project total exceeds CNY 200, execution must stop until a human gives a fresh approval that explicitly names the maximum CNY amount.
- A general request such as “generate the videos” is not an over-threshold budget approval.
- Automatic paid retries are disabled. Any paid retry requires a new approval and its own maximum amount.
- Provider success creates a candidate only; failed identity, speech, continuity or runtime QA does not authorize an automatic regeneration.

## Scoped standing authorization: custom-player portraits (2026-09-09)

The user explicitly selected **Seedance 2.0 Mini / 480p / approximately 10 seconds**, authorized default paid submission when creating a custom character, then instructed: “以后这个 链路无需确认”. For this specific flow, do not ask again for the same generation permission. New role creation submits one task by default; an existing, never-submitted role has one clearly priced submit action, without a second payment-confirmation dialog.

- Keep photo rights/adult consent and candidate likeness review; these are not repeated spending approvals.
- Keep the current conservative local cumulative ceiling of **CNY 5**, with **CNY 2 reserved per task**. This reservation is an experience-based allowance, not a guaranteed provider tariff. Do not silently increase/replenish the ceiling, inherit an old batch allowance, or treat this as unlimited spending authority.
- Keep atomic reservation, request idempotency, one submission per role, and no automatic paid retry. Refresh/configuration recovery must not backfill old roles or duplicate jobs.
- This exception does not authorize different models, broader media batches, production-wide unlimited generation, or deployment. The general project review threshold remains for other media work.
