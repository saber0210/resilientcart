# Trade-offs and Production Roadmap

## Choreography versus orchestration

The project uses event choreography because the workflow is small and it makes service autonomy visible. As the number of steps and compensations grows, a dedicated workflow engine or Saga orchestrator can make state, timeout, and recovery behavior easier to inspect.

## RabbitMQ versus Kafka

RabbitMQ fits task-oriented workflow delivery, per-service queues, delayed retries, and dead-lettering with modest operational complexity. Kafka would be stronger when long event retention, replay, stream processing, or very high append throughput is central.

## PostgreSQL row locks

Row locks provide a clear correctness story for inventory. A flash-sale SKU can become a serialized hotspot. Alternatives include partitioning, an inventory command queue, compare-and-swap versions, or preallocated reservation buckets.

## Outbox polling

Polling is simple and portable but adds publication delay and database reads. Production options include database change-data capture, adaptive polling, partitioned outbox tables, retention jobs, and dedicated publisher replicas.

## Schema management

Services call `create_all` at startup to keep the demo self-contained. Production systems should use reviewed, versioned migrations such as Alembic, separate deploy permissions, backward-compatible schema changes, and rollback plans.

## Secrets and identity

Local credentials are intentionally simple. Production deployment needs a secret manager, TLS, service identity, authorization, network policies, key rotation, audit logging, and least-privilege database roles.

## Availability

The bundled PostgreSQL and RabbitMQ instances are single nodes. A production deployment should use managed or clustered data services, backups, tested restoration, multi-zone scheduling, PodDisruptionBudgets, anti-affinity, and capacity headroom.

## Payment semantics

The payment component is a deterministic simulation. A real integration needs provider idempotency keys, webhook verification, reconciliation, authorization/capture states, refunds, PCI scope management, and careful handling of ambiguous provider timeouts.

## Event contracts

JSON contracts are easy to inspect but not centrally governed. Production systems should add schema compatibility checks, versioned contracts, consumer-driven contract tests, and a documented event-deprecation policy.

## Multi-region

The current design is single-region. Multi-region writes introduce order ownership, inventory allocation, event replication, conflict resolution, latency, and failure-mode complexity. A practical approach is to assign each order and stock partition a home region and use asynchronous cross-region replication for recovery.
