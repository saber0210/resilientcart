# ADR 003: Use a Logical Database per Stateful Service

- Status: Accepted
- Date: 2026-08-17

## Context

Shared tables would allow cross-service joins but would also couple deployments and permit one service to bypass another service's invariants.

## Decision

Order, inventory, payment, and notification services use separate logical PostgreSQL databases. They exchange facts only through APIs and events.

## Consequences

Each service controls its schema and local transaction boundary. Cross-service reports require event-driven projections, an analytics store, or API composition.
