from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    customer_id: str
    amount_cents: int
    status: str
    provider_reference: str | None
    failure_reason: str | None
    created_at: datetime
