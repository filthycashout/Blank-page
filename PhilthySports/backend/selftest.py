from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import app as backend  # noqa: E402


def main() -> None:
    health = backend.health()
    assert health["status"] == "ok"
    assert health["service"] == "PhilthySports"
    assert "live_gate" in health
    assert health["pass_for_live"] is False

    system = backend.system_status()
    assert system["release_state"] in {"V6_SHADOW", "V6_LIVE_EVIDENCE_ROUTED"}
    assert system["gates"]["model_policy"] == "V6_EVIDENCE_ROUTED"
    assert system["gates"]["chronology"] == "PASS"
    assert system["gates"]["calibration"] == "PASS"
    assert system["gates"]["leakage"] == "PASS"
    assert system["gates"]["credential"] == "PASS_KEYLESS_PRIMARY"

    models = backend.models_status()
    assert set(models["sports"]) == {"NFL", "NBA", "MLB", "NHL"}
    assert models["policy"] == "V6_EVIDENCE_ROUTED"
    assert models["sports"]["MLB"]["production_state"] == "V6_PROMOTED_CALIBRATED_MARKET"
    assert models["sports"]["MLB"]["promotion_pass"] is True
    for sport in ("NFL", "NBA", "NHL"):
        state = models["sports"][sport]
        assert state["production_state"] == "V6_MARKET_FALLBACK"
        assert state["candidate_state"] == "V6_CANDIDATE_SHADOW"
        assert state["promotion_pass"] is False
        assert state["promotion_blocker"] == "HOLDOUT_DID_NOT_BEAT_MARKET"

    protocol = backend.protocol()
    assert protocol["master_protocol"][0] == "Understand"
    assert protocol["experiment_loop"][-1] == "Regression Check"

    scheduled = {
        "id": "selftest-game",
        "sport": "NFL",
        "date": "2026-10-02T01:00:00Z",
        "status_name": "STATUS_SCHEDULED",
        "status_text": "Scheduled",
        "state": "pre",
        "home_name": "Home Team",
        "away_name": "Away Team",
        "home_abbr": "HOM",
        "away_abbr": "AWY",
        "home_record": "3-1",
        "away_record": "1-3",
        "home_score": "",
        "away_score": "",
        "home_logo": "",
        "away_logo": "",
    }
    first = backend.predict_game(scheduled).as_dict()
    second = backend.predict_game(scheduled).as_dict()
    assert first == second
    assert 0.29 <= first["home_win_probability"] <= 0.81
    assert "2.5" in first["spread_lean"]
    assert first["projected_outcome"].endswith(first["total_lean"])
    assert backend._strict_upcoming(scheduled) is True

    completed = dict(scheduled, state="post", status_name="STATUS_FINAL")
    assert backend._strict_upcoming(completed) is False

    now = datetime.now(timezone.utc)
    fresh_payload = [{
        "id": "odds-1",
        "home_team": "Home",
        "away_team": "Away",
        "commence_time": (now + timedelta(hours=2)).isoformat(),
        "bookmakers": [{
            "key": "book",
            "title": "Book",
            "last_update": now.isoformat(),
            "markets": [],
        }],
    }]
    accepted, quality = backend._validate_odds_payload(fresh_payload)
    assert len(accepted) == 1
    assert quality["accepted_events"] == 1
    assert quality["fresh_bookmakers"] == 1

    market_event = {
        "id": "market-1",
        "home_team": "Home Club",
        "away_team": "Away Club",
        "commence_time": (now + timedelta(hours=2)).isoformat(),
        "bookmakers": [
            {
                "key": "book-a",
                "last_update": now.isoformat(),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Home Club", "price": -120},
                            {"name": "Away Club", "price": 110},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Home Club", "price": -110, "point": -2.5},
                            {"name": "Away Club", "price": -110, "point": 2.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -110, "point": 47.5},
                            {"name": "Under", "price": -110, "point": 47.5},
                        ],
                    },
                ],
            }
        ],
    }
    built = backend._market_baseline_prediction(market_event, "nfl")
    assert built is not None
    market_game, market_prediction = built
    assert market_game["state"] == "pre"
    assert market_prediction.engine == "De-vigged market consensus baseline v1"
    assert market_prediction.total_lean == "MARKET 47.5"
    assert market_prediction.total_confidence == 0.0
    assert 0 < market_prediction.home_win_probability < 1

    mlb_built = backend._market_baseline_prediction(market_event, "mlb")
    assert mlb_built is not None
    mlb_game, mlb_baseline = mlb_built
    mlb_promoted = backend._v6_calibrated_prediction("mlb", mlb_game, mlb_baseline)
    assert mlb_promoted.engine == "Philthy V6 calibrated market candidate v1"
    assert mlb_promoted.home_win_probability != mlb_baseline.home_win_probability

    retrieved = datetime.now(timezone.utc)
    espn_fixture = {
        "id": "espn-market-1",
        "date": (retrieved + timedelta(hours=3)).isoformat(),
        "competitions": [{
            "id": "espn-market-1",
            "date": (retrieved + timedelta(hours=3)).isoformat(),
            "competitors": [
                {"homeAway": "home", "team": {"displayName": "Home Club"}},
                {"homeAway": "away", "team": {"displayName": "Away Club"}},
            ],
            "odds": [{
                "provider": {"id": "espn", "name": "ESPN BET"},
                "spread": 2.5,
                "overUnder": 47.5,
                "homeTeamOdds": {"favorite": True, "moneyLine": -120},
                "awayTeamOdds": {"favorite": False, "moneyLine": 110},
            }],
        }],
    }
    normalized = backend._espn_market_event(espn_fixture, "nfl", retrieved)
    assert normalized is not None
    assert normalized["data_quality"] == "PREGAME_KEYLESS"
    assert normalized["bookmakers"][0]["markets"][0]["key"] == "h2h"

    parlay_candidates = []
    for i in range(16):
        sport = ("NFL", "NBA", "MLB", "NHL")[i % 4]
        parlay_candidates.append({
            "game_id": f"g-{i}",
            "sport": sport,
            "matchup": f"A{i} @ H{i}",
            "market": "ML",
            "pick": f"P{i}",
            "probability": 0.70 - (i * 0.005),
            "model_state": "V6_MARKET_FALLBACK",
            "reasoning": "fixture reasoning",
        })
    for size in (7, 10, 14):
        built_parlay = backend._build_multisport_parlay(parlay_candidates, size, f"{size}-LEG")
        assert built_parlay["legs"] == size
        assert built_parlay["is_multisport"] is True
        assert len(built_parlay["sports"]) == 4
        assert built_parlay["portfolio_reasoning"]
        assert all(leg["reasoning"] for leg in built_parlay["selections"])

    started_payload = [{
        **fresh_payload[0],
        "id": "odds-started",
        "commence_time": (now - timedelta(minutes=1)).isoformat(),
    }]
    accepted_started, quality_started = backend._validate_odds_payload(started_payload)
    assert accepted_started == []
    assert quality_started["rejected_started_events"] == 1

    stale_payload = [{
        **fresh_payload[0],
        "id": "odds-stale",
        "bookmakers": [{
            "key": "book",
            "title": "Book",
            "last_update": (now - timedelta(hours=2)).isoformat(),
            "markets": [],
        }],
    }]
    accepted_stale, quality_stale = backend._validate_odds_payload(stale_payload)
    assert accepted_stale == []
    assert quality_stale["rejected_stale_events"] == 1

    with tempfile.TemporaryDirectory() as tmp:
        original_ledger = backend.LEDGER_PATH
        backend.LEDGER_PATH = Path(tmp) / "ledger.jsonl"
        try:
            h1 = backend._append_ledger({"event": 1})
            h2 = backend._append_ledger({"event": 2})
            assert h1 and h2 and h1 != h2
            lines = backend.LEDGER_PATH.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 2
            row1 = json.loads(lines[0])
            row2 = json.loads(lines[1])
            assert row1["prev_hash"] == ""
            assert row2["prev_hash"] == row1["record_hash"]
        finally:
            backend.LEDGER_PATH = original_ledger

    latest = backend.predictions_latest()
    assert latest["verified_live_run"] is False
    assert latest["predictions"] == []

    runs = backend.runs_latest()
    assert runs["ledger_mode"] == "append_only_hash_chained_runtime_log"

    print("PhilthySports backend v6 bridge selftest: PASS")


if __name__ == "__main__":
    main()
