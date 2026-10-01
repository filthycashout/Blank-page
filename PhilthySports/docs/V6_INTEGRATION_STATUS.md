# PhilthySports v6 Integration Status

This repository integrates the currently visible v6 governance contract into the working Flutter + FastAPI project without claiming that unavailable external prerequisites have passed.

## Implemented

- NFL, NBA, MLB and NHL Flutter client.
- ESPN schedule/scoreboard ingestion.
- BetP v3 deterministic mobile shadow engine.
- Fixed 2.5 spread behavior, team totals, projected outcome, and 7/10/14-leg parlay presentation.
- FastAPI health, system-status, model-status, predictions, latest-predictions, latest-run, parlay and odds endpoints.
- Explicit `PROVISIONAL_SHADOW`, `CANDIDATE_SHADOW`, and `MARKET_BASELINE_ONLY` states.
- Provider credential rotation gate.
- Fail-closed live-odds endpoint until credential rotation is confirmed.
- SHA-256 source snapshots.
- Append-only hash-chained runtime prediction ledger.
- Backend-only secret handling.
- GitHub Actions backend contract selftest plus Android release build.

## Deliberately not marked complete

The following remain external/data gates rather than fabricated green checks:

1. Provider-side revocation/rotation of legacy exposed credentials.
2. Sufficient clean canonical pregame history for all four sports.
3. Chronological walk-forward candidate promotion against the same market baseline.
4. Production calibration/promotion artifacts with dataset hashes.
5. Persistent deployment storage for ledger/closing-line/settlement data.
6. A deployed production backend URL configured in the APK.

Until those gates pass, the APK remains useful in live-score and shadow-analysis mode and visibly reports the model state instead of presenting the heuristic as a promoted model.
