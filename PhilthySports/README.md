# PhilthySports 1.1

PhilthySports is a Flutter Android client plus a Python API bridge for NFL, NBA, MLB and NHL.

## What works in the APK now

- Live ESPN scoreboards for NFL, NBA, MLB and NHL
- Strict pregame filtering for prediction cards
- Deterministic BetP v3-derived baseline probabilities
- Moneyline conversion
- Fixed 2.5 spread lean logic recovered from the BetP project
- Conservative total lean
- SHA-256 data snapshot provenance
- Multi-sport parlay builder
- Optional backend URL with automatic local fallback
- No private API keys stored in the APK

## Backend

The included FastAPI service provides:

- GET /health
- GET /v1/games/{sport}
- GET /v1/predictions/{sport}
- GET /v1/odds/{sport}

Supported sport keys are nfl, nba, mlb and nhl.

The service reads provider credentials from environment variables. Real values are intentionally not committed.

## Drive-derived configuration slots

The connected project configuration contains variable names for:

- ODDS_API_KEY
- SPORTRADAR_API_KEY
- VISUAL_CROSSING_API_KEY
- GOOGLE_SHEETS_ID
- GCLOUD_PROJECT_ID
- GCLOUD_PRIVATE_KEY_ID
- GCLOUD_PRIVATE_KEY
- GCLOUD_CLIENT_EMAIL
- GCLOUD_CLIENT_ID

## Build

GitHub Actions creates a clean Flutter Android project, copies this source into it, enables Android Internet permission, compiles a release APK and uploads it as the PhilthySports-APK artifact.

## Model note

The mobile baseline intentionally removes Colab-only Drive mounts, interactive cells and nondeterministic notebook randomness. It preserves the visible BetP concepts needed for a usable standalone release. The heavier Powerhouse model stack remains a backend integration target so XGBoost/joblib models and private provider credentials do not have to be embedded inside an Android package.

Prediction output is informational and is not a guarantee of any sporting outcome.


## 1.1 integration pass

- Added BetP v3 home-team and away-team total outputs.
- Added projected outcome field.
- Aligned the deterministic mobile port to the source notebook's bounded probability and O/U ranges while keeping refreshes reproducible.
- Preserved the fixed 2.5 spread behavior.
- Added 7-leg conservative, 10-leg conservative and 14-leg aggressive parlay builders using a $3 model bankroll.
- Added backend tracking metadata and /v1/parlays.
- The visible XGBoost notebook path remains a Python/backend responsibility because its persisted artifact is a joblib model, not an Android-native model format.
- The supplied ChatGPT share URL could not be fetched by this runtime, so no unsupported content from that link was invented.
