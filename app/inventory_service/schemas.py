from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SetStockRequest(BaseModel):
    quantity: int = Field(ge=0, le=1_000_000)


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    available: int
    reserved: int
    sold: int
    updated_at: datetime
