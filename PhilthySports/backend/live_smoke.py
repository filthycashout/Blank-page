from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import app as backend  # noqa: E402


def main() -> None:
    failures: list[str] = []

    for sport in backend.SPORTS:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                games, snapshot = backend.fetch_games(sport, days=1)
                assert isinstance(games, list)
                assert len(snapshot) == 64
                if games:
                    required = {
                        "id",
                        "sport",
                        "date",
                        "status_name",
                        "state",
                        "home_name",
                        "away_name",
                        "home_abbr",
                        "away_abbr",
                    }
                    missing = required.difference(games[0])
                    assert not missing, f"missing fields: {sorted(missing)}"
                print(f"{sport.upper()}: PASS ({len(games)} events, snapshot {snapshot[:10]})")
                last_error = None
                break
            except Exception as exc:  # network smoke with bounded retries
                last_error = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)

        if last_error is not None:
            failures.append(f"{sport.upper()}: {last_error}")

    if failures:
        raise SystemExit("Live ESPN smoke failed:\n" + "\n".join(failures))

    print("Live ESPN smoke: PASS for NFL/NBA/MLB/NHL")


if __name__ == "__main__":
    main()
