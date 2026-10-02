# PhilthySports v6 Integration Status

## Current state

The project now runs the production policy `V6_EVIDENCE_ROUTED` on the deployed Powerhouse backend:

`https://philthysports-powerhouse.onrender.com`

The APK uses that HTTPS endpoint by default and only enters on-device `PROVISIONAL_SHADOW` when the user explicitly selects local mode.

## Gates

Methodology gates are reproduced in CI from a pinned historical corpus:

- Chronology: `PASS`
- Calibration: `PASS`
- Leakage: `PASS`
- Active credential gate: `PASS_KEYLESS_PRIMARY`

The active credential gate passes because the selected production market source is the keyless ESPN pregame market feed. This does not mark old exposed secret-provider credentials as rotated.

Legacy secret-provider rotation remains `BLOCKED_EXTERNAL_ROTATION` until the credentials are revoked/reissued at their providers.

## Sport routing

The v6 evidence audit uses chronological 60/20/20 train, calibration, and untouched-holdout windows and compares each calibrated candidate with its de-vigged market baseline on the same holdout.

- MLB: `V6_PROMOTED_CALIBRATED_MARKET`
- NFL: `V6_MARKET_FALLBACK` + `V6_CANDIDATE_SHADOW`
- NBA: `V6_MARKET_FALLBACK` + `V6_CANDIDATE_SHADOW`
- NHL: `V6_MARKET_FALLBACK` + `V6_CANDIDATE_SHADOW`

NFL, NBA, and NHL are not force-promoted because their tested candidates did not beat the market on the untouched holdout.

## Evidence provenance

Pinned source repository:
`flancast90/sportsbookreview-scraper`

Pinned commit:
`1a820e50c6fbd0276cde073c22bfffae78930868`

Per-sport Git blob hashes and holdout metrics are recorded in:
`backend/evidence/v6_evidence.json`

The build executes:
`python backend/v6_evidence_audit.py`

The audit rejects source hash drift or metric drift.

## Parlays

`/v1/parlays` builds 7-, 10-, and 14-leg multisport sets with:
- cross-sport round-robin selection,
- one leg per game before any fallback,
- strict pregame filtering,
- v6 model state attached to every leg,
- per-leg reasoning,
- portfolio reasoning,
- an explicit `INDEPENDENCE_FALLBACK` warning.

## Deployment verification

Release CI probes the actual public Powerhouse URL and requires:
- API version `1.3.0-v6-evidence-routed`,
- chronology/calibration/leakage PASS,
- active credential PASS,
- `V6_EVIDENCE_ROUTED`,
- live gate enabled,
- MLB promotion evidence present,
- NFL/NBA/NHL fallback states preserved,
- keyless ESPN market endpoint responding.

## Still external

The following are not faked green:
1. Provider-side rotation of the old exposed Odds API/Sportradar/etc credentials before reuse.
2. A newer 2026 historical retraining/revalidation corpus.
3. Durable immutable ledger storage outside Render's ephemeral `/tmp`.
4. Measured parlay dependency modeling beyond the current independence fallback.
5. Google Play production signing/AAB publication if store distribution is desired.
