from __future__ import annotations

import sys
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

    latest = backend.predictions_latest()
    assert latest["verified_live_run"] is False
    assert latest["predictions"] == []

    runs = backend.runs_latest()
    assert runs["ledger_mode"] == "append_only_hash_chained_runtime_log"

    print("PhilthySports backend v6 bridge selftest: PASS")


if __name__ == "__main__":
    main()
