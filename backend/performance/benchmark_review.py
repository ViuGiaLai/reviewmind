"""Repeatable local benchmark for the deterministic review pipeline."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.review import ReviewEngine, ReviewRequest


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def document(words: int) -> str:
    paragraph = (
        "This benchmark paragraph presents a claim, supporting evidence, "
        "and a concise explanation for deterministic review performance. "
    )
    repeated = (paragraph * max(1, words // len(paragraph.split())))[: words * 8]
    return f"# Introduction\n\n{repeated}\n\n# Methodology\n\n{repeated}\n\n# References\n\nExample (2026)."


def _summary(latencies: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.fmean(latencies), 2),
        "p50": round(percentile(latencies, 0.50), 2),
        "p95": round(percentile(latencies, 0.95), 2),
        "p99": round(percentile(latencies, 0.99), 2),
        "max": round(max(latencies), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--words", type=int, default=5000)
    parser.add_argument("--p95-budget-ms", type=float, default=2000)
    args = parser.parse_args()

    engine = ReviewEngine(enable_ai=False)
    base_text = document(args.words)
    warm_request = ReviewRequest(
        text=base_text, filename="benchmark.md", profile_id="academic",
        review_mode="rule_only",
    )
    engine.review(warm_request)

    cold_latencies: list[float] = []
    for index in range(args.runs):
        request = ReviewRequest(
            text=f"{base_text}\n\nRun marker {index}",
            filename=f"benchmark-{index}.md",
            profile_id="academic",
            review_mode="rule_only",
        )
        started = time.perf_counter()
        engine.review(request)
        cold_latencies.append((time.perf_counter() - started) * 1000)

    warm_latencies: list[float] = []
    for _ in range(args.runs):
        started = time.perf_counter()
        engine.review(warm_request)
        warm_latencies.append((time.perf_counter() - started) * 1000)

    result = {
        "runs_per_mode": args.runs,
        "target_words": args.words,
        "cold_latency_ms": _summary(cold_latencies),
        "warm_latency_ms": _summary(warm_latencies),
    }
    print(json.dumps(result, indent=2))
    return 1 if result["cold_latency_ms"]["p95"] > args.p95_budget_ms else 0

if __name__ == "__main__":
    raise SystemExit(main())
