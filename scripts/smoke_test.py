#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from uuid import uuid4

import httpx

TERMINAL = {"COMPLETED", "REJECTED", "PAYMENT_FAILED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a ResilientCart smoke test")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--customer-id", default="smoke-test")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        stock = client.put("/api/inventory/SKU-CHAIR", json={"quantity": 100})
        stock.raise_for_status()

        response = client.post(
            "/api/checkout",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "customer_id": args.customer_id,
                "item_id": "SKU-CHAIR",
                "quantity": 1,
                "amount_cents": 4999,
            },
        )
        response.raise_for_status()
        order = response.json()
        order_id = order["id"]
        print(f"Created order {order_id} in state {order['status']}")

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            current = client.get(f"/api/orders/{order_id}")
            current.raise_for_status()
            order = current.json()
            print(f"Order state: {order['status']}")
            if order["status"] in TERMINAL:
                print(order)
                expected = "PAYMENT_FAILED" if args.customer_id.endswith("-fail") else "COMPLETED"
                if order["status"] != expected:
                    print(f"Expected {expected}, got {order['status']}", file=sys.stderr)
                    return 1
                return 0
            time.sleep(0.5)

    print("Timed out waiting for a terminal state", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
