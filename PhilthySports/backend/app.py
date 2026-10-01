from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(
    title="PhilthySports API",
    version="1.2.1-final-audit",
    description="Unified NFL, NBA, MLB and NHL prediction bridge.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

SPORTS = {
    "nfl": ("football", "nfl", "americanfootball_nfl"),
    "nba": ("basketball", "nba", "basketball_nba"),
    "mlb": ("baseball", "mlb", "baseball_mlb"),
    "nhl": ("hockey", "nhl", "icehockey_nhl"),
}

KNOWN_MLB_STRENGTH = {
    "NYY": 0.78,
    "LAD": 0.80,
    "PHI": 0.72,
    "MIL": 0.68,
    "ATL": 0.73,
    "HOU": 0.70,
    "SD": 0.59,
    "TOR": 0.67,
    "BOS": 0.71,
    "STL": 0.63,
    "CLE": 0.67,
    "DET": 0.58,
    "SF": 0.65,
    "TEX": 0.66,
    "SEA": 0.64,
    "CHC": 0.69,
    "WSH": 0.57,
    "KC": 0.41,
    "MIA": 0.42,
    "OAK": 0.41,
    "LAA": 0.40,
    "COL": 0.38,
    "PIT": 0.50,
    "BAL": 0.48,
    "TB": 0.65,
    "MIN": 0.51,
    "CWS": 0.48,
    "CIN": 0.48,
    "ARI": 0.51,
    "NYM": 0.54,
}

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ODDS_BASE = "https://api.the-odds-api.com/v4"
ODDS_MAX_AGE_MINUTES = int(os.getenv("ODDS_MAX_AGE_MINUTES", "15"))
MASTER_PROTOCOL = [
    "Understand",
    "Decompose",
    "Inspect",
    "Map",
    "Challenge",
    "Plan",
    "Act",
    "Verify",
    "Recalibrate",
    "Explain",
    "Retain",
    "Improve",
]

EXPERIMENT_LOOP = [
    "Evidence",
    "Hypothesis",
    "Smallest Experiment",
    "Result",
    "Update",
    "Regression Check",
]

OPERATING_SEQUENCE = [
    "Secure",
    "Ingest",
    "Validate",
    "Version",
    "Train",
    "Promote/Shadow",
    "Freeze Live Snapshot",
    "Predict",
    "Ledger",
    "Capture Close",
    "Settle",
    "CLV",
    "Recalibrate",
    "Verify",
    "Release",
]

_cache: dict[str, tuple[float, Any, str]] = {}

RUNTIME_DIR = Path(os.getenv("PHILTHY_RUNTIME_DIR", "/tmp/philthysports"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_PATH = RUNTIME_DIR / "prediction_ledger.jsonl"

_latest_run: dict[str, Any] | None = None
_latest_verified_predictions: list[dict[str, Any]] = []


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _rotation_confirmed() -> bool:
    return _truthy_env("CREDENTIAL_ROTATION_CONFIRMED")


def _production_live_enabled() -> bool:
    return _rotation_confirmed() and _truthy_env("PHILTHY_LIVE_ENABLED")


def _provider_state() -> dict[str, bool]:
    return {
        "odds_api_configured": bool(os.getenv("ODDS_API_KEY")),
        "sportradar_configured": bool(os.getenv("SPORTRADAR_API_KEY")),
        "visual_crossing_configured": bool(os.getenv("VISUAL_CROSSING_API_KEY")),
        "google_sheets_configured": bool(os.getenv("GOOGLE_SHEETS_ID")),
        "google_cloud_configured": bool(os.getenv("GCLOUD_PROJECT_ID")),
    }


def _system_gates() -> dict[str, Any]:
    providers = _provider_state()
    rotation = _rotation_confirmed()
    return {
        "credential_rotation": "PASS" if rotation else "BLOCKED_EXTERNAL_ROTATION",
        "canonical_history": "AWAITING_CANONICAL_HISTORY",
        "live_data_qa": (
            "READY_FOR_PREFLIGHT"
            if rotation and providers["odds_api_configured"]
            else "BLOCKED_MISSING_ROTATED_CREDENTIAL"
        ),
        "model_policy": "MARKET_BASELINE_ONLY",
        "parlay_dependency": "INDEPENDENCE_FALLBACK",
        "settlement": "READY_WITH_DATA",
        "closing_line_clv": "READY_WITH_DATA",
        "pass_for_live": bool(
            rotation
            and providers["odds_api_configured"]
            and _truthy_env("PHILTHY_LIVE_ENABLED")
        ),
    }


def _last_ledger_hash() -> str:
    if not LEDGER_PATH.exists():
        return ""
    try:
        lines = LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        if not lines:
            return ""
        last = json.loads(lines[-1])
        return str(last.get("record_hash") or "")
    except Exception:
        return ""


def _append_ledger(record: dict[str, Any]) -> str:
    prev_hash = _last_ledger_hash()
    body = dict(record)
    body["prev_hash"] = prev_hash
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    record_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    body["record_hash"] = record_hash
    with LEDGER_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body, sort_keys=True) + "\n")
    return record_hash


@dataclass(frozen=True)
class Prediction:
    home_win_probability: float
    pick: str
    pick_confidence: float
    moneyline: int
    spread_lean: str
    total_lean: str
    total_confidence: float
    home_team_total: str
    away_team_total: str
    projected_outcome: str
    engine: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "home_win_probability": round(self.home_win_probability, 6),
            "pick": self.pick,
            "pick_confidence": round(self.pick_confidence, 6),
            "moneyline": self.moneyline,
            "spread_lean": self.spread_lean,
            "total_lean": self.total_lean,
            "total_confidence": round(self.total_confidence, 6),
            "home_team_total": self.home_team_total,
            "away_team_total": self.away_team_total,
            "projected_outcome": self.projected_outcome,
            "engine": self.engine,
        }


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> tuple[Any, str]:
    cached = _cache.get(url)
    now = time.time()
    if cached and (now - cached[0]) < CACHE_TTL:
        return cached[1], cached[2]

    response = requests.get(
        url,
        headers=headers or {"User-Agent": "PhilthySports/1.0"},
        timeout=18,
    )
    response.raise_for_status()
    body = response.text
    payload = response.json()
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    _cache[url] = (now, payload, digest)
    return payload, digest


def _record_summary(competitor: dict[str, Any]) -> str:
    records = competitor.get("records") or []
    if records and isinstance(records[0], dict):
        return str(records[0].get("summary") or "")
    return ""


def _parse_event(event: dict[str, Any], sport_key: str) -> dict[str, Any] | None:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competition = competitions[0] if isinstance(competitions[0], dict) else {}
    competitors = competition.get("competitors") or []
    if not competitors:
        return None

    home = next(
        (c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "home"),
        competitors[0],
    )
    away = next(
        (c for c in competitors if isinstance(c, dict) and c.get("homeAway") == "away"),
        competitors[1] if len(competitors) > 1 else competitors[0],
    )
    if not isinstance(home, dict) or not isinstance(away, dict):
        return None

    home_team = home.get("team") if isinstance(home.get("team"), dict) else {}
    away_team = away.get("team") if isinstance(away.get("team"), dict) else {}
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    status_type = status.get("type") if isinstance(status.get("type"), dict) else {}

    return {
        "id": str(event.get("id") or ""),
        "sport": sport_key.upper(),
        "date": event.get("date"),
        "status_name": str(status_type.get("name") or ""),
        "status_text": str(
            status_type.get("shortDetail")
            or status_type.get("detail")
            or ""
        ),
        "state": str(status_type.get("state") or ""),
        "home_name": str(home_team.get("displayName") or home_team.get("name") or "Home"),
        "away_name": str(away_team.get("displayName") or away_team.get("name") or "Away"),
        "home_abbr": str(home_team.get("abbreviation") or ""),
        "away_abbr": str(away_team.get("abbreviation") or ""),
        "home_record": _record_summary(home),
        "away_record": _record_summary(away),
        "home_score": str(home.get("score") or ""),
        "away_score": str(away.get("score") or ""),
        "home_logo": str(home_team.get("logo") or ""),
        "away_logo": str(away_team.get("logo") or ""),
    }


def fetch_games(sport_key: str, days: int = 2) -> tuple[list[dict[str, Any]], str]:
    if sport_key not in SPORTS:
        raise HTTPException(status_code=404, detail="Unsupported sport")

    espn_sport, league, _ = SPORTS[sport_key]
    by_id: dict[str, dict[str, Any]] = {}
    digests: list[str] = []

    today = datetime.now(timezone.utc)
    for offset in range(days):
        date_str = (today + timedelta(days=offset)).strftime("%Y%m%d")
        url = (
            f"{ESPN_BASE}/{espn_sport}/{league}/scoreboard"
            f"?lang=en&region=us&dates={date_str}"
        )
        try:
            payload, digest = _get_json(url)
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"ESPN fetch failed: {exc}") from exc

        digests.append(digest)
        for event in payload.get("events", []) if isinstance(payload, dict) else []:
            if not isinstance(event, dict):
                continue
            game = _parse_event(event, sport_key)
            if game and game["id"]:
                by_id[game["id"]] = game

    games = sorted(by_id.values(), key=lambda g: str(g.get("date") or ""))
    combined = hashlib.sha256("".join(digests).encode("utf-8")).hexdigest()
    return games, combined


def _record_strength(record: str) -> float:
    nums: list[int] = []
    current = ""
    for char in record:
        if char.isdigit():
            current += char
        elif current:
            nums.append(int(current))
            current = ""
    if current:
        nums.append(int(current))

    if len(nums) < 2:
        return 0.5

    wins = float(nums[0])
    losses = float(nums[1])
    extras = float(sum(nums[2:])) if len(nums) > 2 else 0.0
    total = wins + losses + extras
    if total <= 0:
        return 0.5
    return max(0.15, min(0.85, wins / total))


def _uniform(game_id: str, salt: str, low: float, high: float) -> float:
    digest = hashlib.md5(f"{game_id}|{salt}".encode("utf-8")).hexdigest()[:8]
    unit = int(digest, 16) / 0xFFFFFFFF
    return low + ((high - low) * unit)


def _moneyline(probability: float) -> int:
    if probability <= 0 or probability >= 1:
        return 0
    if probability >= 0.5:
        return round(-100 * probability / (1 - probability))
    return round(100 * (1 - probability) / probability)


def _american_implied_probability(price: Any) -> float | None:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value < 0:
        return abs(value) / (abs(value) + 100.0)
    return 100.0 / (value + 100.0)


def _fair_american_moneyline(probability: float) -> int:
    probability = min(0.999, max(0.001, probability))
    if probability >= 0.5:
        return round(-100 * probability / (1 - probability))
    return round(100 * (1 - probability) / probability)


def _format_point(value: float) -> str:
    return f"{value:+g}"


def _team_code(name: str) -> str:
    tokens = [token for token in name.replace("-", " ").split() if token]
    if not tokens:
        return "TEAM"
    if len(tokens) == 1:
        return tokens[0][:4].upper()
    initials = "".join(token[0] for token in tokens)
    return initials[:4].upper()


def _market_baseline_prediction(
    event: dict[str, Any],
    sport_key: str,
) -> tuple[dict[str, Any], Prediction] | None:
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    if not home or not away:
        return None

    fair_home_samples: list[float] = []
    home_spreads: list[float] = []
    away_spreads: list[float] = []
    totals: list[float] = []

    for book in event.get("bookmakers") or []:
        if not isinstance(book, dict):
            continue
        for market in book.get("markets") or []:
            if not isinstance(market, dict):
                continue
            key = str(market.get("key") or "")
            outcomes = [
                outcome
                for outcome in (market.get("outcomes") or [])
                if isinstance(outcome, dict)
            ]

            if key == "h2h":
                by_name = {str(o.get("name") or ""): o for o in outcomes}
                home_price = by_name.get(home, {}).get("price")
                away_price = by_name.get(away, {}).get("price")
                hp = _american_implied_probability(home_price)
                ap = _american_implied_probability(away_price)
                if hp is not None and ap is not None and (hp + ap) > 0:
                    fair_home_samples.append(hp / (hp + ap))

            elif key == "spreads":
                by_name = {str(o.get("name") or ""): o for o in outcomes}
                try:
                    if home in by_name and by_name[home].get("point") is not None:
                        home_spreads.append(float(by_name[home]["point"]))
                    if away in by_name and by_name[away].get("point") is not None:
                        away_spreads.append(float(by_name[away]["point"]))
                except (TypeError, ValueError):
                    pass

            elif key == "totals":
                for outcome in outcomes:
                    if outcome.get("point") is None:
                        continue
                    try:
                        totals.append(float(outcome["point"]))
                    except (TypeError, ValueError):
                        continue

    if not fair_home_samples:
        return None

    home_probability = float(statistics.median(fair_home_samples))
    pick = home if home_probability >= 0.53 else away if home_probability <= 0.47 else "PASS"
    selected_probability = max(home_probability, 1 - home_probability)

    if pick == "PASS":
        fair_moneyline = 0
    else:
        fair_moneyline = _fair_american_moneyline(selected_probability)

    home_spread = statistics.median(home_spreads) if home_spreads else None
    away_spread = statistics.median(away_spreads) if away_spreads else None
    if pick == home and home_spread is not None:
        spread = f"{_team_code(home)} {_format_point(home_spread)}"
    elif pick == away and away_spread is not None:
        spread = f"{_team_code(away)} {_format_point(away_spread)}"
    else:
        spread = "MARKET N/A"

    market_total = statistics.median(totals) if totals else None
    total_lean = f"MARKET {market_total:g}" if market_total is not None else "MARKET N/A"
    side = _team_code(home) if home_probability > 0.5 else _team_code(away)

    game = {
        "id": str(event.get("id") or ""),
        "sport": sport_key.upper(),
        "date": event.get("commence_time"),
        "status_name": "STATUS_SCHEDULED",
        "status_text": "Scheduled · fresh market",
        "state": "pre",
        "home_name": home,
        "away_name": away,
        "home_abbr": _team_code(home),
        "away_abbr": _team_code(away),
        "home_record": "",
        "away_record": "",
        "home_score": "",
        "away_score": "",
        "home_logo": "",
        "away_logo": "",
    }

    prediction = Prediction(
        home_win_probability=home_probability,
        pick=pick if pick == "PASS" else _team_code(pick),
        pick_confidence=selected_probability,
        moneyline=fair_moneyline,
        spread_lean=spread,
        total_lean=total_lean,
        total_confidence=0.0,
        home_team_total="MARKET N/A",
        away_team_total="MARKET N/A",
        projected_outcome=f"{side} ML · MARKET_BASELINE",
        engine="De-vigged market consensus baseline v1",
    )
    return game, prediction


def predict_game(game: dict[str, Any]) -> Prediction:
    home_record = _record_strength(str(game.get("home_record") or ""))
    away_record = _record_strength(str(game.get("away_record") or ""))

    home_strength = home_record
    away_strength = away_record
    sport = str(game.get("sport") or "").upper()

    if sport == "MLB":
        h = KNOWN_MLB_STRENGTH.get(str(game.get("home_abbr") or ""))
        a = KNOWN_MLB_STRENGTH.get(str(game.get("away_abbr") or ""))
        if h is not None:
            home_strength = (h * 0.55) + (home_record * 0.45)
        if a is not None:
            away_strength = (a * 0.55) + (away_record * 0.45)

    home_advantage = {
        "NFL": 0.035,
        "NBA": 0.030,
        "MLB": 0.025,
        "NHL": 0.020,
    }.get(sport, 0.025)

    rating_diff = home_strength - away_strength
    base = 1.0 / (1.0 + math.exp(-5.5 * (rating_diff + home_advantage)))

    # BetP v3 uses bounded random variance. For serving, derive the same
    # bounded ranges from the event id so repeated requests are reproducible.
    home_probability = max(
        0.29,
        min(
            0.81,
            base + _uniform(str(game.get("id") or ""), "ml", -0.065, 0.065),
        ),
    )

    if home_probability >= 0.53:
        pick = str(game.get("home_abbr") or "HOME")
    elif home_probability <= 0.47:
        pick = str(game.get("away_abbr") or "AWAY")
    else:
        pick = "PASS"

    pick_probability = max(home_probability, 1 - home_probability)
    moneyline = 0 if pick == "PASS" else _moneyline(pick_probability)

    # Source behavior: fixed 2.5 spread, no alternate spread number.
    if home_probability > 0.55:
        spread = f"{game.get('home_abbr') or 'HOME'} -2.5"
    else:
        spread = f"{game.get('away_abbr') or 'AWAY'} +2.5"

    over_probability = max(
        0.36,
        min(
            0.83,
            (home_probability * 0.34)
            + _uniform(str(game.get("id") or ""), "ou", 0.39, 0.71),
        ),
    )
    total_lean = "OVER" if over_probability > 0.523 else "UNDER"
    total_confidence = max(
        0.38,
        min(0.92, abs(over_probability - 0.5) * 2.25),
    )

    home_team_total = (
        "OVER 2.5"
        if home_probability > 0.52 and over_probability > 0.5
        else "UNDER 2.5"
    )
    away_team_total = (
        "OVER 2.5"
        if (1 - home_probability) > 0.52 and over_probability > 0.5
        else "UNDER 2.5"
    )
    side = (
        str(game.get("home_abbr") or "HOME")
        if home_probability > 0.5
        else str(game.get("away_abbr") or "AWAY")
    )
    projected_outcome = f"{side} ML + {total_lean}"

    return Prediction(
        home_win_probability=home_probability,
        pick=pick,
        pick_confidence=pick_probability,
        moneyline=moneyline,
        spread_lean=spread,
        total_lean=total_lean,
        total_confidence=total_confidence,
        home_team_total=home_team_total,
        away_team_total=away_team_total,
        projected_outcome=projected_outcome,
        engine="Philthy Shadow v1.2 · BetP v3 deterministic port",
    )


def _strict_upcoming(game: dict[str, Any]) -> bool:
    state = str(game.get("state") or "").lower()
    if state:
        return state == "pre"
    status = str(game.get("status_name") or "").upper()
    blocked = (
        "FINAL",
        "COMPLETE",
        "FULL_TIME",
        "IN_PROGRESS",
        "HALFTIME",
        "END",
        "POSTPONED",
    )
    if any(item in status for item in blocked):
        return False
    return any(item in status for item in ("SCHEDULED", "PRE", "TBD"))


@app.get("/health")
def health() -> dict[str, Any]:
    gates = _system_gates()
    return {
        "status": "ok",
        "service": "PhilthySports",
        "version": "1.2.1-final-audit",
        "engine": os.getenv("PHILTHY_ENGINE_MODE", "provisional_shadow"),
        "live_gate": gates["credential_rotation"],
        "pass_for_live": gates["pass_for_live"],
        "providers": _provider_state(),
    }


@app.get("/v1/system/status")
def system_status() -> dict[str, Any]:
    return {
        "service": "PhilthySports",
        "version": "1.2.1-final-audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gates": _system_gates(),
        "release_state": (
            "LIVE_ENABLED" if _production_live_enabled() else "SHADOW_BASELINE_ONLY"
        ),
        "principle": "fail_closed_on_unverified_external_prerequisites",
    }


@app.get("/v1/protocol")
def protocol() -> dict[str, Any]:
    return {
        "master_protocol": MASTER_PROTOCOL,
        "experiment_loop": EXPERIMENT_LOOP,
        "operating_sequence": OPERATING_SEQUENCE,
    }


@app.get("/v1/models/status")
def models_status() -> dict[str, Any]:
    sports = {}
    for sport in SPORTS:
        sports[sport.upper()] = {
            "production_state": "MARKET_BASELINE_ONLY",
            "candidate_state": "CANDIDATE_SHADOW",
            "promotion_blocker": "AWAITING_CANONICAL_HISTORY",
            "minimum_canonical_rows": 200,
            "promotion_requires": [
                "chronological_holdout",
                "brier_improvement",
                "non_inferior_log_loss",
                "acceptable_ece",
                "no_leakage_blocker",
                "artifact_and_dataset_hashes",
            ],
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sports": sports,
    }


@app.get("/v1/predictions/latest")
def predictions_latest() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_live_run": _production_live_enabled(),
        "predictions": list(_latest_verified_predictions)
        if _production_live_enabled()
        else [],
        "note": (
            "Latest verified live predictions"
            if _production_live_enabled()
            else "Empty by design until live security/data gates are explicitly enabled."
        ),
    }


@app.get("/v1/runs/latest")
def runs_latest() -> dict[str, Any]:
    return {
        "latest_run": _latest_run,
        "ledger_path": str(LEDGER_PATH),
        "ledger_mode": "append_only_hash_chained_runtime_log",
    }


@app.get("/v1/games/{sport}")
def games(
    sport: str,
    days: int = Query(2, ge=1, le=7),
) -> dict[str, Any]:
    sport_key = sport.lower()
    data, snapshot = fetch_games(sport_key, days)
    return {
        "sport": sport_key.upper(),
        "snapshot_sha256": snapshot,
        "games": data,
    }


@app.get("/v1/predictions/{sport}")
def predictions(
    sport: str,
    days: int = Query(2, ge=1, le=7),
) -> dict[str, Any]:
    global _latest_run, _latest_verified_predictions

    sport_key = sport.lower()
    generated_at = datetime.now(timezone.utc).isoformat()
    gates = _system_gates()

    if _production_live_enabled():
        market_events, market_quality, quota = _fetch_live_odds(sport_key)
        rows: list[dict[str, Any]] = []
        snapshot = hashlib.sha256(
            json.dumps(market_events, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        for event in market_events:
            built = _market_baseline_prediction(event, sport_key)
            if built is None:
                continue
            game, prediction_obj = built
            prediction = prediction_obj.as_dict()
            ledger_record = {
                "recorded_at": generated_at,
                "sport": sport_key.upper(),
                "event_id": game.get("id"),
                "event_time": game.get("date"),
                "source_snapshot_sha256": snapshot,
                "model_state": "MARKET_BASELINE",
                "engine": prediction["engine"],
                "game": game,
                "prediction": prediction,
            }
            ledger_hash = _append_ledger(ledger_record)
            rows.append({
                "game": game,
                "prediction": prediction,
                "ledger": {
                    "record_hash": ledger_hash,
                    "source_snapshot_sha256": snapshot,
                },
            })

        payload = {
            "sport": sport_key.upper(),
            "generated_at": generated_at,
            "engine": "De-vigged market consensus baseline v1",
            "model_state": "MARKET_BASELINE",
            "snapshot_sha256": snapshot,
            "predictions": rows,
            "tracking": {
                "games_predicted": len(rows),
                "source": "The Odds API",
                "quality": market_quality,
                "quota": quota,
                "generated_at": generated_at,
            },
            "governance": {
                "mode": "production_baseline",
                "model_state": "MARKET_BASELINE",
                "production_policy": "MARKET_BASELINE_ONLY",
                "promotion_blocker": "AWAITING_CANONICAL_HISTORY",
                "credential_gate": gates["credential_rotation"],
                "pass_for_live": gates["pass_for_live"],
                "private_provider_keys_embedded_in_apk": False,
            },
        }
        _latest_verified_predictions = rows
    else:
        data, snapshot = fetch_games(sport_key, days)
        rows = []
        for game in data:
            if not _strict_upcoming(game):
                continue
            prediction = predict_game(game).as_dict()
            ledger_record = {
                "recorded_at": generated_at,
                "sport": sport_key.upper(),
                "event_id": game.get("id"),
                "event_time": game.get("date"),
                "source_snapshot_sha256": snapshot,
                "model_state": "PROVISIONAL_SHADOW",
                "engine": prediction["engine"],
                "game": game,
                "prediction": prediction,
            }
            ledger_hash = _append_ledger(ledger_record)
            rows.append({
                "game": game,
                "prediction": prediction,
                "ledger": {
                    "record_hash": ledger_hash,
                    "source_snapshot_sha256": snapshot,
                },
            })

        payload = {
            "sport": sport_key.upper(),
            "generated_at": generated_at,
            "engine": "Philthy Shadow v1.2 · BetP v3 deterministic port",
            "model_state": "PROVISIONAL_SHADOW",
            "snapshot_sha256": snapshot,
            "predictions": rows,
            "tracking": {
                "games_predicted": len(rows),
                "filter": "strict upcoming only",
                "spread_used": "exactly 2.5",
                "parlay_sizes": [7, 10, 14],
                "bankroll_usd": 3.0,
                "generated_at": generated_at,
            },
            "governance": {
                "mode": "shadow",
                "model_state": "PROVISIONAL_SHADOW",
                "production_policy": "MARKET_BASELINE_ONLY",
                "promotion_blocker": "AWAITING_CANONICAL_HISTORY",
                "credential_gate": gates["credential_rotation"],
                "pass_for_live": gates["pass_for_live"],
                "private_provider_keys_embedded_in_apk": False,
            },
        }

    _latest_run = {
        "sport": sport_key.upper(),
        "generated_at": generated_at,
        "games_predicted": len(payload["predictions"]),
        "snapshot_sha256": payload["snapshot_sha256"],
        "model_state": payload["model_state"],
        "pass_for_live": gates["pass_for_live"],
    }
    return payload


@app.get("/v1/parlays")
def parlays(days: int = Query(2, ge=1, le=7)) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    snapshots: list[str] = []

    for sport_key in SPORTS:
        games, snapshot = fetch_games(sport_key, days)
        snapshots.append(snapshot)
        for game in games:
            if not _strict_upcoming(game):
                continue

            prediction = predict_game(game)
            matchup = f"{game.get('away_abbr')} @ {game.get('home_abbr')}"

            if prediction.pick != "PASS":
                candidates.append({
                    "sport": sport_key.upper(),
                    "matchup": matchup,
                    "market": "ML",
                    "pick": prediction.pick,
                    "probability": prediction.pick_confidence,
                })

            if prediction.home_win_probability > 0.58:
                candidates.append({
                    "sport": sport_key.upper(),
                    "matchup": matchup,
                    "market": "SPREAD 2.5",
                    "pick": f"{game.get('home_abbr')} -2.5",
                    "probability": min(0.68, prediction.home_win_probability + 0.04),
                })

            away_probability = 1 - prediction.home_win_probability
            if away_probability > 0.58:
                candidates.append({
                    "sport": sport_key.upper(),
                    "matchup": matchup,
                    "market": "SPREAD 2.5",
                    "pick": f"{game.get('away_abbr')} +2.5",
                    "probability": min(0.68, away_probability + 0.04),
                })

    candidates.sort(key=lambda item: item["probability"], reverse=True)

    def build(size: int, name: str) -> dict[str, Any]:
        legs = candidates[:size]
        true_probability = 1.0
        for leg in legs:
            true_probability *= float(leg["probability"])
        decimal = round(1.0 / max(0.0001, true_probability), 2) if legs else 0.0
        return {
            "name": name,
            "legs": len(legs),
            "target_legs": size,
            "model_joint_probability": round(true_probability, 8) if legs else 0.0,
            "est_decimal_odds": decimal,
            "bankroll_usd": 3.0,
            "est_payout_usd": round(3.0 * decimal, 2),
            "selections": legs,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_sha256": hashlib.sha256("".join(snapshots).encode("utf-8")).hexdigest(),
        "parlays": {
            "7_leg_conservative": build(7, "7-LEG CONSERVATIVE"),
            "10_leg_conservative": build(10, "10-LEG CONSERVATIVE"),
            "14_leg_aggressive": build(14, "14-LEG AGGRESSIVE"),
        },
    }


def _parse_provider_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_odds_payload(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=502, detail="Odds provider returned an invalid schema.")

    now = datetime.now(timezone.utc)
    accepted: list[dict[str, Any]] = []
    rejected_schema = 0
    rejected_started = 0
    rejected_stale = 0
    fresh_bookmakers = 0
    stale_bookmakers = 0

    for raw in payload:
        if not isinstance(raw, dict):
            rejected_schema += 1
            continue

        if not all(raw.get(key) for key in ("id", "home_team", "away_team", "commence_time")):
            rejected_schema += 1
            continue

        commence_time = _parse_provider_time(raw.get("commence_time"))
        if commence_time is None:
            rejected_schema += 1
            continue
        if commence_time <= now:
            rejected_started += 1
            continue

        bookmakers = raw.get("bookmakers")
        if not isinstance(bookmakers, list) or not bookmakers:
            rejected_stale += 1
            continue

        fresh: list[dict[str, Any]] = []
        for book in bookmakers:
            if not isinstance(book, dict):
                continue
            updated = _parse_provider_time(book.get("last_update"))
            if updated is None:
                stale_bookmakers += 1
                continue
            age_minutes = max(0.0, (now - updated).total_seconds() / 60.0)
            if age_minutes <= ODDS_MAX_AGE_MINUTES:
                item = dict(book)
                item["age_minutes"] = round(age_minutes, 2)
                fresh.append(item)
                fresh_bookmakers += 1
            else:
                stale_bookmakers += 1

        if not fresh:
            rejected_stale += 1
            continue

        event = dict(raw)
        event["bookmakers"] = fresh
        event["data_quality"] = "FRESH"
        accepted.append(event)

    return accepted, {
        "schema_valid": rejected_schema == 0,
        "accepted_events": len(accepted),
        "rejected_schema_events": rejected_schema,
        "rejected_started_events": rejected_started,
        "rejected_stale_events": rejected_stale,
        "fresh_bookmakers": fresh_bookmakers,
        "stale_bookmakers": stale_bookmakers,
        "max_bookmaker_age_minutes": ODDS_MAX_AGE_MINUTES,
    }


def _fetch_live_odds(
    sport_key: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if sport_key not in SPORTS:
        raise HTTPException(status_code=404, detail="Unsupported sport")
    if not _rotation_confirmed():
        raise HTTPException(
            status_code=503,
            detail="Live odds blocked until provider credential rotation is confirmed.",
        )

    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="ODDS_API_KEY is not configured on the server",
        )

    _, _, odds_sport = SPORTS[sport_key]
    url = f"{ODDS_BASE}/sports/{odds_sport}/odds/"
    params = {
        "apiKey": key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }
    try:
        response = requests.get(url, params=params, timeout=18)
        response.raise_for_status()
        events, quality = _validate_odds_payload(response.json())
        quota = {
            "requests_remaining": response.headers.get("x-requests-remaining"),
            "requests_used": response.headers.get("x-requests-used"),
            "requests_last": response.headers.get("x-requests-last"),
        }
        return events, quality, quota
    except HTTPException:
        raise
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        raise HTTPException(
            status_code=502,
            detail=f"Odds provider request failed (status={status or 'network'}).",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Odds provider returned malformed JSON.",
        ) from exc


@app.get("/v1/odds/{sport}")
def odds(sport: str) -> dict[str, Any]:
    sport_key = sport.lower()
    events, quality, quota = _fetch_live_odds(sport_key)
    return {
        "sport": sport_key.upper(),
        "provider": "The Odds API",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "quality": quality,
        "quota": quota,
        "events": events,
    }
