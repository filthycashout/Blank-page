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
    assert system["release_state"] in {"SHADOW_BASELINE_ONLY", "LIVE_ENABLED"}
    assert system["gates"]["model_policy"] == "MARKET_BASELINE_ONLY"

    models = backend.models_status()
    assert set(models["sports"]) == {"NFL", "NBA", "MLB", "NHL"}
    for state in models["sports"].values():
        assert state["production_state"] == "MARKET_BASELINE_ONLY"
        assert state["candidate_state"] == "CANDIDATE_SHADOW"

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
