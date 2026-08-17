# Architecture and Event Contracts

## Goals

ResilientCart demonstrates how a checkout workflow can remain correct when services fail independently, HTTP clients retry requests, and a message broker delivers an event more than once.

The design prioritizes explainability and correctness over feature breadth. Each stateful service owns its data, communicates asynchronously through domain events, and treats message delivery as at least once.

## Components

### API Gateway

Provides the public HTTP surface and an interactive browser demo. It forwards the `Idempotency-Key` header to the order service and does not own business state.

### Order Service

Owns the order lifecycle. Creating an order inserts both the `PENDING` order and an `order.created` outbox record in one database transaction. It listens for inventory and payment outcomes and emits completion or compensation events.

### Inventory Service

Owns stock and reservations. It locks one inventory row with `SELECT ... FOR UPDATE`, verifies available stock, and updates available, reserved, and sold quantities atomically. A failed payment causes an `inventory.release` compensation.

### Payment Service

Owns payment attempts. `order_id` is the business idempotency key, ensuring an order cannot be charged twice in this simulation. Customer IDs ending in `-fail` produce a deterministic decline for demos.

### Notification Service

Stores durable completion and failure notifications. `event_id` is the primary key, making duplicate delivery harmless.

### RabbitMQ

Carries persistent domain events. Every consumer has a durable main queue, a delayed retry queue, and a dead-letter queue. Consumers acknowledge messages only after their local database transaction commits.

## Event envelope

Every event has the following shape:

```json
{
  "event_id": "UUID",
  "event_type": "inventory.reserved",
  "aggregate_id": "order UUID",
  "correlation_id": "workflow UUID",
  "occurred_at": "ISO-8601 timestamp",
  "trace_context": {
    "traceparent": "W3C trace context"
  },
  "payload": {}
}
```

`event_id` supports consumer deduplication, `aggregate_id` identifies the order, `correlation_id` links logs, and `trace_context` propagates OpenTelemetry context across asynchronous boundaries.

## Domain events

| Event | Producer | Consumers | Meaning |
|---|---|---|---|
| `order.created` | Order | Inventory | A durable order has been accepted |
| `inventory.reserved` | Inventory | Order, Payment | Required stock is reserved |
| `inventory.rejected` | Inventory | Order | Stock cannot be reserved |
| `payment.succeeded` | Payment | Order | The simulated provider accepted payment |
| `payment.failed` | Payment | Order | The simulated provider declined payment |
| `inventory.release` | Order | Inventory | Compensate a previously reserved order |
| `inventory.commit` | Order | Inventory | Convert a paid reservation into sold stock |
| `inventory.released` | Inventory | Observability / future consumers | Compensation completed |
| `inventory.committed` | Inventory | Observability / future consumers | Paid stock was finalized |
| `order.completed` | Order | Notification | Checkout reached its success terminal state |
| `order.failed` | Order | Notification | Checkout reached a failed terminal state |

## Transactional outbox

A service never writes business state and publishes directly to RabbitMQ in the same request. Instead it commits business state and an outbox row together. A background publisher locks unpublished rows, publishes persistent messages, and marks the rows as published.

A crash after publication but before marking the row can produce a duplicate event. This is expected; consumers record processed `event_id` values or enforce a unique business key.

## Consistency model

The system provides strong consistency inside one service database and eventual consistency across services. A newly accepted order may remain `PENDING` briefly while asynchronous work completes. Clients poll the order resource or could be extended to use WebSockets or server-sent events.

## Ordering

The workflow does not assume global message ordering. State transitions are monotonic and terminal states do not move backward. A production implementation could add an aggregate version to each event and reject stale versions explicitly.

## Scaling

API services can scale horizontally behind a load balancer. RabbitMQ distributes messages among competing consumers on the same queue. PostgreSQL row locks serialize reservations for one SKU while allowing unrelated SKUs to proceed concurrently.

The hottest SKU can become a contention point. Production alternatives include partitioned inventory, reservation tokens, single-writer actors per SKU, or a dedicated high-throughput inventory ledger.
