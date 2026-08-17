from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    order_id: str
    customer_id: str
    kind: str
    message: str
    created_at: datetime
