from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateOrderRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=128)
    item_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=100)
    amount_cents: int = Field(ge=1, le=100_000_000)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    idempotency_key: str
    customer_id: str
    item_id: str
    quantity: int
    amount_cents: int
    status: str
    reason: str | None
    correlation_id: str
    created_at: datetime
    updated_at: datetime
