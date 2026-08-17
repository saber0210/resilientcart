# Benchmark Results

This file is a reproducibility template. Do not add numbers until you have run the workload yourself.

## Environment

| Field | Value |
|---|---|
| Date | `YYYY-MM-DD` |
| Git commit | `[commit SHA]` |
| Machine / cloud instance | `[model or instance type]` |
| CPU | `[vCPU count and model]` |
| Memory | `[GB]` |
| Operating system | `[name and version]` |
| Docker version | `[version]` |
| Test duration | `[minutes]` |
| Locust users | `[count]` |
| Spawn rate | `[users/second]` |

## Results

| Metric | Result |
|---|---:|
| Total requests | `[value]` |
| Requests per second | `[value]` |
| Median latency | `[value] ms` |
| p95 latency | `[value] ms` |
| p99 latency | `[value] ms` |
| HTTP failure rate | `[value] %` |
| Completed checkouts | `[value]` |
| Duplicate orders | `[value]` |
| Lost orders | `[value]` |

## Correctness experiments

| Experiment | Input | Expected invariant | Observed result |
|---|---|---|---|
| Idempotency | 50 requests with one key | One order ID | `[result]` |
| Inventory contention | 1,000 attempts, 100 units | 100 completed; zero overselling | `[result]` |
| Payment decline | Customer ID ending `-fail` | Inventory released | `[result]` |
| Payment-service interruption | Stop and restart consumer | Queued order completes after recovery | `[result]` |

## Commands

```bash
python scripts/duplicate_test.py --requests 50
python scripts/contention_test.py --attempts 1000 --stock 100
python scripts/smoke_test.py --customer-id benchmark-fail
locust -f load-tests/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 10m --host http://localhost:8080 --csv benchmark-results/load
```

Attach raw CSV files or a summarized chart in a release or a `benchmark-results` branch rather than committing large generated files to `main`.
