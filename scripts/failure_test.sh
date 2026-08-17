#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"

echo "Stopping payment-service to create a recoverable partial failure..."
docker compose stop payment-service

BASE_URL="$BASE_URL" python - <<'PY'
import os
import httpx
from uuid import uuid4
base = os.environ["BASE_URL"]
try:
    response = httpx.post(
        f"{base}/api/checkout",
        headers={"Idempotency-Key": str(uuid4())},
        json={"customer_id":"failure-test","item_id":"SKU-CHAIR","quantity":1,"amount_cents":4999},
        timeout=15,
    )
    response.raise_for_status()
    print("ORDER_ID=" + response.json()["id"])
except Exception as exc:
    print(f"Gateway request failed while payment was stopped: {exc}")
PY

echo "Restarting payment-service. RabbitMQ should deliver the queued inventory.reserved event."
docker compose start payment-service

echo "Inspect the order in the web UI, RabbitMQ queues, Jaeger traces, and Grafana dashboard."
echo "Web UI: ${BASE_URL}"
