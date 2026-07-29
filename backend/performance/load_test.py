"""Dependency-free HTTP load/stress runner for ReviewMind.

Example:
  python performance/load_test.py --url http://localhost:8000/live -c 25 -n 1000
  python performance/load_test.py --url http://localhost:8000/api/dashboard \
      --token "$TOKEN" -c 20 -n 500 --p95-budget-ms 500
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def request_once(
    url: str,
    method: str,
    token: str,
    body: bytes | None,
    timeout: float,
) -> tuple[float, int, str]:
    headers = {"Accept": "application/json", "X-Load-Test": "reviewmind"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return (time.perf_counter() - started) * 1000, response.status, ""
    except urllib.error.HTTPError as error:
        error.read()
        return (time.perf_counter() - started) * 1000, error.code, str(error)
    except Exception as error:
        return (time.perf_counter() - started) * 1000, 0, str(error)


def run(args: argparse.Namespace) -> dict[str, Any]:
    body = Path(args.body_file).read_bytes() if args.body_file else None
    latencies: list[float] = []
    statuses: dict[int, int] = {}
    errors: list[str] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(
                request_once, args.url, args.method, args.token, body, args.timeout
            )
            for _ in range(args.requests)
        ]
        for future in as_completed(futures):
            latency, status, error = future.result()
            latencies.append(latency)
            statuses[status] = statuses.get(status, 0) + 1
            if error:
                errors.append(error)

    duration = time.perf_counter() - started
    failures = sum(count for status, count in statuses.items() if status < 200 or status >= 400)
    return {
        "url": args.url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "duration_seconds": round(duration, 3),
        "throughput_rps": round(args.requests / duration, 2) if duration else 0,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0,
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "max": round(max(latencies), 2) if latencies else 0,
        },
        "statuses": statuses,
        "failure_rate": round(failures / args.requests, 4) if args.requests else 0,
        "sample_errors": errors[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("-n", "--requests", type=int, default=500)
    parser.add_argument("-c", "--concurrency", type=int, default=20)
    parser.add_argument("--method", choices=("GET", "POST"), default="GET")
    parser.add_argument("--token", default="")
    parser.add_argument("--body-file", default="")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--p95-budget-ms", type=float, default=1000)
    parser.add_argument("--max-failure-rate", type=float, default=0.01)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")

    result = run(args)
    print(json.dumps(result, indent=2))
    failed = (
        result["latency_ms"]["p95"] > args.p95_budget_ms
        or result["failure_rate"] > args.max_failure_rate
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
