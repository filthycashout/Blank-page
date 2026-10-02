# PhilthySports 1.3

PhilthySports is a Flutter Android client plus a FastAPI Powerhouse backend for NFL, NBA, MLB and NHL.

## Production URL

The deployed Powerhouse API is:

`https://philthysports-powerhouse.onrender.com`

The APK uses this URL by default. Local mode is an explicit opt-out in Settings, not a silent fallback.

## v6 evidence-routed production

Production policy is `V6_EVIDENCE_ROUTED`.

The release pipeline reproduces a pinned historical evidence audit before building the APK. The audit:
- verifies pinned Git blob hashes,
- sorts games chronologically,
- uses a 60% / 20% / 20% train-calibration-untouched-holdout split,
- excludes final scores and in-game fields from prediction features,
- tunes calibration only on the calibration window,
- compares the candidate with the same de-vigged market probability on the untouched holdout.

Current evidence route:
- MLB: `V6_PROMOTED_CALIBRATED_MARKET`
- NFL: `V6_MARKET_FALLBACK`, candidate remains shadowed
- NBA: `V6_MARKET_FALLBACK`, candidate remains shadowed
- NHL: `V6_MARKET_FALLBACK`, candidate remains shadowed

The fallback states are intentional. Their historical candidates did not beat the market on the untouched holdout, so v6 does not promote them.

Evidence is stored in `backend/evidence/v6_evidence.json` and reproduced by `backend/v6_evidence_audit.py`.

## Live market and credentials

The active primary live-market source is the keyless ESPN pregame market feed. The active credential gate is therefore `PASS_KEYLESS_PRIMARY` and no provider secret is embedded in the APK.

Previously exposed Odds API / Sportradar / other provider credentials are not reused. Their separate legacy rotation status remains blocked until those credentials are revoked and newly issued at their providers. A future secret-backed provider can be enabled server-side only after that rotation.

## Multisport parlays

The backend and APK expose 7-, 10-, and 14-leg multisport parlays.

Selection rules:
- strict pregame games only,
- moneyline legs only in the governed parlay pool,
- rotate across available NFL/NBA/MLB/NHL games,
- prefer one leg per game,
- rank by qualified side confidence,
- attach a reason to each leg and a portfolio-level reason.

Joint probability uses `INDEPENDENCE_FALLBACK`. It is explicitly not presented as proof that parlay legs are statistically independent.

## Backend endpoints

- `GET /`
- `GET /health`
- `GET /v1/system/status`
- `GET /v1/protocol`
- `GET /v1/models/status`
- `GET /v1/games/{sport}`
- `GET /v1/predictions/{sport}`
- `GET /v1/predictions/latest`
- `GET /v1/runs/latest`
- `GET /v1/parlays`
- `GET /v1/odds/{sport}`

Supported sport keys are `nfl`, `nba`, `mlb`, and `nhl`.

## Release verification

GitHub Actions must pass:
- source secret scan,
- Python compilation,
- reproducible v6 evidence audit,
- backend v6 contract self-test,
- four-sport ESPN smoke test,
- backend container smoke test,
- public Powerhouse HTTPS smoke test,
- `flutter analyze`,
- Flutter tests,
- release APK build,
- APK signature verification,
- checksum generation.

## Remaining external limitations

- Legacy exposed provider credentials still need provider-side revocation/rotation before any of those secret-backed providers can be reused.
- The historical promotion corpus currently ends in 2021/2022 depending on sport. The evidence is valid for the tested historical holdout, but it is not represented as a 2026 retraining corpus.
- The free Render service can cold-start after an idle period.
- Runtime ledger storage under `/tmp` is ephemeral. Durable immutable storage still requires a persistent data service or object-lock/WORM destination.
- Google Play publication would require the Play signing/AAB release flow rather than only the sideloadable APK.

Prediction output is informational and is not a guarantee of a sporting outcome.
