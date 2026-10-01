from __future__ import annotations

import hashlib
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(
    title="PhilthySports API",
    version="1.0.0",
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

_cache: dict[str, tuple[float, Any, str]] = {}


@dataclass(frozen=True)
class Prediction:
    home_win_probability: float
    pick: str
    pick_confidence: float
    moneyline: int
    spread_lean: str
    total_lean: str
    total_confidence: float
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


def _jitter(game_id: str) -> float:
    digest = hashlib.md5(game_id.encode("utf-8")).hexdigest()[:4]
    unit = int(digest, 16) / 65535.0
    return (unit - 0.5) * 0.035


def _moneyline(probability: float) -> int:
    if probability <= 0 or probability >= 1:
        return 0
    if probability >= 0.5:
        return round(-100 * probability / (1 - probability))
    return round(100 * (1 - probability) / probability)


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
    home_probability = max(
        0.29,
        min(0.81, base + _jitter(str(game.get("id") or ""))),
    )

    if home_probability >= 0.53:
        pick = str(game.get("home_abbr") or "HOME")
    elif home_probability <= 0.47:
        pick = str(game.get("away_abbr") or "AWAY")
    else:
        pick = "PASS"

    pick_probability = max(home_probability, 1 - home_probability)
    moneyline = 0 if pick == "PASS" else _moneyline(pick_probability)

    if home_probability > 0.55:
        spread = f"{game.get('home_abbr') or 'HOME'} -2.5"
    elif home_probability < 0.45:
        spread = f"{game.get('away_abbr') or 'AWAY'} +2.5"
    else:
        spread = "PASS"

    over_probability = max(
        0.36,
        min(
            0.83,
            0.49
            + ((pick_probability - 0.5) * 0.32)
            + (_jitter(str(game.get("id") or "")) * 0.25),
        ),
    )
    total_lean = "OVER lean" if over_probability > 0.523 else "UNDER lean"
    total_confidence = max(
        0.38,
        min(0.92, abs(over_probability - 0.5) * 2.25),
    )

    return Prediction(
        home_win_probability=home_probability,
        pick=pick,
        pick_confidence=pick_probability,
        moneyline=moneyline,
        spread_lean=spread,
        total_lean=total_lean,
        total_confidence=total_confidence,
        engine="Philthy Baseline v1 · BetP v3-derived",
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
    return {
        "status": "ok",
        "service": "PhilthySports",
        "version": "1.0.0",
        "engine": os.getenv("PHILTHY_ENGINE_MODE", "baseline"),
        "providers": {
            "odds_api_configured": bool(os.getenv("ODDS_API_KEY")),
            "sportradar_configured": bool(os.getenv("SPORTRADAR_API_KEY")),
            "visual_crossing_configured": bool(os.getenv("VISUAL_CROSSING_API_KEY")),
            "google_sheets_configured": bool(os.getenv("GOOGLE_SHEETS_ID")),
            "google_cloud_configured": bool(os.getenv("GCLOUD_PROJECT_ID")),
        },
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
    sport_key = sport.lower()
    data, snapshot = fetch_games(sport_key, days)
    rows = []
    for game in data:
        if not _strict_upcoming(game):
            continue
        rows.append(
            {
                "game": game,
                "prediction": predict_game(game).as_dict(),
            }
        )

    return {
        "sport": sport_key.upper(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "Philthy Baseline v1 · BetP v3-derived",
        "snapshot_sha256": snapshot,
        "predictions": rows,
        "governance": {
            "mode": "baseline",
            "powerhouse_bridge": "ready_for_deployment",
            "private_provider_keys_embedded_in_apk": False,
        },
    }


@app.get("/v1/odds/{sport}")
def odds(sport: str) -> dict[str, Any]:
    sport_key = sport.lower()
    if sport_key not in SPORTS:
        raise HTTPException(status_code=404, detail="Unsupported sport")

    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="ODDS_API_KEY is not configured on the server",
        )

    _, _, odds_sport = SPORTS[sport_key]
    url = (
        f"{ODDS_BASE}/sports/{odds_sport}/odds/"
        f"?apiKey={key}&regions=us&markets=h2h,spreads,totals&oddsFormat=american"
    )
    try:
        response = requests.get(url, timeout=18)
        response.raise_for_status()
        return {
            "sport": sport_key.upper(),
            "provider": "The Odds API",
            "events": response.json(),
        }
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Odds fetch failed: {exc}") from exc
