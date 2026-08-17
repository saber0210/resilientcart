from __future__ import annotations

from uuid import uuid4

from locust import HttpUser, between, task


class Shopper(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        self.order_ids: list[str] = []

    @task(5)
    def browse_inventory(self) -> None:
        self.client.get("/api/inventory/SKU-CHAIR", name="GET /api/inventory/:item")

    @task(3)
    def checkout(self) -> None:
        response = self.client.post(
            "/api/checkout",
            name="POST /api/checkout",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "customer_id": f"load-{uuid4().hex[:10]}",
                "item_id": "SKU-CHAIR",
                "quantity": 1,
                "amount_cents": 4999,
            },
        )
        if response.ok and response.json().get("id"):
            self.order_ids.append(response.json()["id"])
            self.order_ids = self.order_ids[-20:]

    @task(2)
    def check_order(self) -> None:
        if not self.order_ids:
            return
        order_id = self.order_ids[-1]
        self.client.get(f"/api/orders/{order_id}", name="GET /api/orders/:id")
