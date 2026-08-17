#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from uuid import uuid4

import httpx

TERMINAL = {"COMPLETED", "REJECTED", "PAYMENT_FAILED"}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Test inventory contention without overselling")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--attempts", type=int, default=1000)
    parser.add_argument("--stock", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=50)
    timeout = httpx.Timeout(30.0)
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout, limits=limits) as client:
        response = await client.put(
            "/api/inventory/SKU-CONTENTION",
            json={"quantity": args.stock},
        )
        response.raise_for_status()

        async def create_order(index: int) -> str:
            async with semaphore:
                response = await client.post(
                    "/api/checkout",
                    headers={"Idempotency-Key": str(uuid4())},
                    json={
                        "customer_id": f"contention-{index}",
                        "item_id": "SKU-CONTENTION",
                        "quantity": 1,
                        "amount_cents": 1000,
                    },
                )
                response.raise_for_status()
                return response.json()["id"]

        order_ids = await asyncio.gather(
            *(create_order(index) for index in range(args.attempts))
        )

        async def wait_for_order(order_id: str) -> str:
            deadline = asyncio.get_running_loop().time() + args.timeout
            while asyncio.get_running_loop().time() < deadline:
                async with semaphore:
                    response = await client.get(f"/api/orders/{order_id}")
                response.raise_for_status()
                status = response.json()["status"]
                if status in TERMINAL:
                    return status
                await asyncio.sleep(0.25)
            return "TIMEOUT"

        statuses = await asyncio.gather(*(wait_for_order(order_id) for order_id in order_ids))
        inventory_deadline = asyncio.get_running_loop().time() + 30
        while True:
            inventory = (await client.get("/api/inventory/SKU-CONTENTION")).json()
            if inventory["reserved"] == 0 or asyncio.get_running_loop().time() >= inventory_deadline:
                break
            await asyncio.sleep(0.25)

    counts = Counter(statuses)
    print(f"Attempts: {args.attempts}")
    print(f"Initial stock: {args.stock}")
    print(f"Final inventory: {inventory}")
    print(f"Terminal states: {dict(counts)}")

    passed = (
        counts["COMPLETED"] == args.stock
        and counts["REJECTED"] == args.attempts - args.stock
        and inventory["available"] == 0
        and inventory["reserved"] == 0
        and inventory["sold"] == args.stock
        and counts["TIMEOUT"] == 0
    )
    print("PASS: zero overselling" if passed else "FAIL: review results")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
