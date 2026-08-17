# Capacity-Estimation Worksheet

The numbers below are planning assumptions, not benchmark results.

## Example workload assumptions

| Variable | Example assumption |
|---|---:|
| Registered users | 1,000,000 |
| Daily active users | 100,000 |
| Peak active fraction | 10% |
| Product/API requests per active user at peak | 20 per hour |
| Checkout conversion | 2% |
| Peak multiplier over daily average | 5x |

## Request estimate

Peak browsing request rate:

```text
100,000 DAU × 10% active at peak × 20 requests/hour ÷ 3,600
≈ 56 requests/second
```

Apply a 5x safety and campaign multiplier:

```text
56 × 5 ≈ 280 requests/second
```

Peak checkout rate at a 2% conversion:

```text
280 × 2% ≈ 6 checkouts/second
```

Each successful checkout produces approximately five domain-event deliveries: order creation, inventory result, payment result, order completion, and notification. Include retries and observability overhead when sizing RabbitMQ and databases.

## Storage estimate

Assume 500,000 orders per month and roughly 2 KB per order including indexes and metadata:

```text
500,000 × 2 KB ≈ 1 GB/month for core order rows
```

Outbox, processed-event, payment, reservation, notification, and audit data can multiply this by several times. Apply retention rules and archive old workflow metadata.

## Latency budget example

| Stage | Budget |
|---|---:|
| Gateway and order write | 100 ms |
| Outbox publication | 250 ms |
| Inventory handling | 100 ms |
| Payment provider | 500 ms |
| Final order update | 250 ms |
| End-to-end checkout state | 1.2 s target |

Measure each stage with traces rather than inferring end-to-end latency from HTTP response time; the initial checkout endpoint intentionally returns before the Saga completes.

## Bottlenecks to investigate

1. Row-lock contention for a flash-sale SKU.
2. RabbitMQ queue lag when payment processing is slower than inventory reservation.
3. PostgreSQL connection-pool saturation.
4. Outbox backlog after a broker outage.
5. Trace and log volume at higher throughput.

Use the Locust CSV, Prometheus time series, RabbitMQ queue depth, PostgreSQL statistics, and Jaeger traces to identify the first bottleneck on your test environment.
