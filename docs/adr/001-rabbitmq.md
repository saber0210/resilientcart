# ADR 001: Use RabbitMQ for Domain Events

- Status: Accepted
- Date: 2026-08-17

## Context

The checkout workflow needs durable asynchronous delivery, competing consumers, delayed retries, and dead-letter queues. The project must remain runnable on a graduate developer's laptop.

## Decision

Use one durable RabbitMQ topic exchange for domain events. Each service owns a durable queue, retry queue, and dead-letter queue.

## Consequences

The workflow and failure behavior are easy to demonstrate. RabbitMQ does not provide the same long-term replay and stream-processing model as Kafka, so event replay would require additional retention or an event store.
