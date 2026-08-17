# ADR 002: Use a Choreographed Saga

- Status: Accepted
- Date: 2026-08-17

## Context

Checkout spans order, inventory, payment, and notification data without a shared ACID transaction.

## Decision

Represent each successful step and failure as a domain event. The order service records the business state and emits compensation events when payment fails.

## Consequences

Services remain loosely coupled and the event flow demonstrates eventual consistency. Workflow understanding is distributed across handlers, so documentation, correlation IDs, and traces are essential.
