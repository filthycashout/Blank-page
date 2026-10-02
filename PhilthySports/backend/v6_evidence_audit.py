from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "evidence" / "v6_evidence.json"
TEMPS = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
BIASES = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]


def implied(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    return abs(value) / (abs(value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def clamp(value, lo=1e-9, hi=1 - 1e-9):
    return max(lo, min(hi, value))


def logit(p):
    p = clamp(p)
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def log_loss(rows, key):
    total = 0.0
    for row in rows:
        p = clamp(row[key])
        total -= row["y"] * math.log(p) + (1 - row["y"]) * math.log(1 - p)
    return total / len(rows)


def brier(rows, key):
    return sum((row[key] - row["y"]) ** 2 for row in rows) / len(rows)


def ece(rows, key, bins=10):
    total = 0.0
    for index in range(bins):
        lo, hi = index / bins, (index + 1) / bins
        bucket = [
            row for row in rows
            if row[key] >= lo and (row[key] <= hi if index == bins - 1 else row[key] < hi)
        ]
        if not bucket:
            continue
        confidence = sum(row[key] for row in bucket) / len(bucket)
        accuracy = sum(row["y"] for row in bucket) / len(bucket)
        total += (len(bucket) / len(rows)) * abs(confidence - accuracy)
    return total


def git_blob_sha(body: bytes) -> str:
    header = f"blob {len(body)}\0".encode()
    return hashlib.sha1(header + body).hexdigest()


def load_rows(body: bytes):
    raw = json.loads(body)
    rows = []
    for index, item in enumerate(raw):
        hp = implied(item.get("home_close_ml"))
        ap = implied(item.get("away_close_ml"))
        try:
            home_score = float(item.get("home_final"))
            away_score = float(item.get("away_final"))
            date = float(item.get("date"))
        except (TypeError, ValueError):
            continue
        if hp is None or ap is None or home_score == away_score:
            continue
        rows.append({
            "index": index,
            "date": date,
            "y": 1 if home_score > away_score else 0,
            "market": hp / (hp + ap),
        })
    rows.sort(key=lambda row: (row["date"], row["index"]))
    return rows


def score_candidate(rows, temperature, bias):
    return [
        {
            **row,
            "candidate": sigmoid(temperature * logit(row["market"]) + bias),
        }
        for row in rows
    ]


def audit_sport(manifest, sport, cfg):
    commit = manifest["source"]["commit"]
    path = cfg["dataset_path"]
    url = f"https://raw.githubusercontent.com/{manifest['source']['repository']}/{commit}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "PhilthySports-v6-evidence-audit"})
    last_error = None
    body = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    if body is None:
        raise RuntimeError(f"{sport}: could not fetch pinned evidence source") from last_error

    actual_sha = git_blob_sha(body)
    assert actual_sha == cfg["blob_sha"], f"{sport}: source blob hash changed"

    rows = load_rows(body)
    cut1 = math.floor(len(rows) * 0.60)
    cut2 = math.floor(len(rows) * 0.80)
    calibration = rows[cut1:cut2]
    holdout = rows[cut2:]

    best = None
    for temperature in TEMPS:
        for bias in BIASES:
            candidate = score_candidate(calibration, temperature, bias)
            score = log_loss(candidate, "candidate")
            if best is None or score < best[0]:
                best = (score, temperature, bias)

    _, temperature, bias = best
    evaluated = score_candidate(holdout, temperature, bias)
    metrics = {
        "rows": len(rows),
        "train_rows": cut1,
        "calibration_rows": cut2 - cut1,
        "holdout_rows": len(rows) - cut2,
        "temperature": temperature,
        "bias": bias,
        "candidate_brier": brier(evaluated, "candidate"),
        "market_brier": brier(evaluated, "market"),
        "candidate_log_loss": log_loss(evaluated, "candidate"),
        "market_log_loss": log_loss(evaluated, "market"),
        "candidate_ece": ece(evaluated, "candidate"),
        "market_ece": ece(evaluated, "market"),
    }
    metrics["brier_improvement"] = metrics["market_brier"] - metrics["candidate_brier"]
    metrics["log_loss_delta"] = metrics["candidate_log_loss"] - metrics["market_log_loss"]
    metrics["promotion_pass"] = bool(
        metrics["rows"] >= manifest["methodology"]["promotion_rule"]["minimum_rows"]
        and metrics["candidate_brier"] < metrics["market_brier"]
        and metrics["candidate_log_loss"] <= metrics["market_log_loss"]
        and metrics["candidate_ece"] <= manifest["methodology"]["promotion_rule"]["ece_max"]
    )

    exact_fields = ("rows", "train_rows", "calibration_rows", "holdout_rows", "temperature", "bias", "promotion_pass")
    for field in exact_fields:
        assert metrics[field] == cfg[field], f"{sport}: {field} drifted: {metrics[field]} != {cfg[field]}"

    metric_fields = (
        "candidate_brier", "market_brier", "brier_improvement",
        "candidate_log_loss", "market_log_loss", "log_loss_delta",
        "candidate_ece", "market_ece",
    )
    for field in metric_fields:
        assert abs(metrics[field] - cfg[field]) <= 0.000002, (
            f"{sport}: {field} drifted: {metrics[field]:.8f} != {cfg[field]:.8f}"
        )

    return metrics


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["methodology"]["chronology_gate"] == "PASS"
    assert manifest["methodology"]["calibration_gate"] == "PASS"
    assert manifest["methodology"]["leakage_gate"] == "PASS"

    results = {}
    for sport, cfg in manifest["sports"].items():
        results[sport] = audit_sport(manifest, sport, cfg)

    assert results["MLB"]["promotion_pass"] is True
    assert all(results[s]["promotion_pass"] is False for s in ("NFL", "NBA", "NHL"))
    print("PhilthySports v6 chronology/calibration/leakage evidence audit: PASS")
    print(json.dumps({sport: {"promotion_pass": row["promotion_pass"]} for sport, row in results.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
