# Failure Scenarios

| Failure | Expected behavior | Evidence to collect |
|---|---|---|
| Client retries checkout | Unique idempotency key returns the original order | Duplicate-test output and one order row |
| Order service crashes after DB commit | Outbox row remains and is published after restart | Outbox row, event, and eventual state transition |
| Publisher crashes after broker publish | Event may be published twice; consumer deduplicates | Same business result with duplicate event deliveries |
| Inventory has insufficient stock | Order becomes `REJECTED`; payment is never attempted | Trace and order state |
| Two consumers reserve one SKU | Row lock serializes updates; available stock never becomes negative and paid reservations become sold stock | Contention-test result |
| Payment is declined | Order becomes `PAYMENT_FAILED`; `inventory.release` restores stock | Before/after inventory and trace |
| Payment consumer is stopped | RabbitMQ retains `inventory.reserved`; processing resumes after restart | Queue depth and eventual completion |
| Handler throws repeatedly | Message enters delayed retries, then the service DLQ | RabbitMQ queue inspection |
| RabbitMQ is unavailable | Business write and outbox commit succeed; publisher retries later | Unpublished outbox row and recovery |
| Notification service is unavailable | Core order completion is unaffected; notification waits in its queue | Completed order and queued message |

## Failure-injection procedure

For each experiment, record:

- Commit SHA and environment.
- Exact command and failure start time.
- Number of affected orders.
- Queue depth and outbox backlog.
- Recovery time.
- Lost, duplicated, or inconsistent business operations.
- A trace or log correlation ID.

Run each scenario multiple times before turning it into a resume claim.
