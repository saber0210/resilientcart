#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

import httpx


async def main() -> int:
    parser = argparse.ArgumentParser(description="Verify HTTP idempotency")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=50)
    args = parser.parse_args()

    key = str(uuid4())
    payload = {
        "customer_id": "duplicate-test",
        "item_id": "SKU-CHAIR",
        "quantity": 1,
        "amount_cents": 4999,
    }
    async with httpx.AsyncClient(base_url=args.base_url, timeout=20) as client:
        await client.put("/api/inventory/SKU-CHAIR", json={"quantity": 100})

        async def send() -> str:
            response = await client.post(
                "/api/checkout",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            response.raise_for_status()
            return response.json()["id"]

        order_ids = await asyncio.gather(*(send() for _ in range(args.requests)))

    unique_ids = set(order_ids)
    print(f"Requests sent: {args.requests}")
    print(f"Unique order IDs: {len(unique_ids)}")
    print(f"Order ID: {next(iter(unique_ids))}")
    return 0 if len(unique_ids) == 1 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
