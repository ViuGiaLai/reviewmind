# Chapter 21 – Performance Engineering & Scalability

Production objectives:

- Read-only API p95 under 500 ms and error rate below 1%.
- Rule-only review p95 under 2 s for a 5,000-word text document.
- Bounded memory: uploads stop at the configured limit and rule cache is LRU-bounded.
- Bounded concurrency: excess reviews receive `503` with `Retry-After` instead of exhausting workers.
- PostgreSQL uses one thread-safe connection pool per process with a statement timeout.

## Measured baseline

Local development baseline (2026-07-29; results vary by hardware):

- `/live`: 500 requests at concurrency 25, 415.15 req/s, p95 74.92 ms, p99 79.75 ms, 0% failures.
- 5,000-word rule review: cold p95 196.43 ms; warm p95 11.16 ms across 20 runs.
- Initial frontend JavaScript: 452.11 kB raw / 129.89 kB gzip after lazy loading, down about 8.95% gzip.

Run a local review benchmark:

```bash
cd backend
python performance/benchmark_review.py --runs 30 --words 5000
```

Run API load testing:

```bash
python performance/load_test.py --url http://localhost:8000/live -c 25 -n 1000
python performance/load_test.py --url http://localhost:8000/api/dashboard \
  --token "$TOKEN" -c 20 -n 500 --p95-budget-ms 500
```

Prometheus can calculate p95/p99 from the emitted
`reviewmind_http_request_duration_seconds_bucket` histogram. Capacity should be
increased horizontally when CPU remains above 70%, pool wait p95 rises, or
review rejections persist.