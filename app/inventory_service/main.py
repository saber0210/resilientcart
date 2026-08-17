from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.common.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from app.common.messaging import ReliableConsumer
from app.common.metrics import instrument_fastapi
from app.common.outbox import OutboxPublisher
from app.common.telemetry import configure_tracing
from app.inventory_service.models import Base, InventoryItem, OutboxEvent
from app.inventory_service.schemas import SetStockRequest, StockResponse
from app.inventory_service.service import handle_domain_event, set_stock

SERVICE_NAME = "inventory-service"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@postgres:5432/inventorydb",
)
AMQP_URL = os.getenv("AMQP_URL", "amqp://resilientcart:resilientcart@rabbitmq:5672/%2F")

engine = create_database_engine(DATABASE_URL)
SessionLocal = create_session_factory(engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def consume_event(event: dict) -> None:
    session = SessionLocal()
    try:
        handle_domain_event(session, event)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(engine, Base)
    seed_session = SessionLocal()
    try:
        if seed_session.get(InventoryItem, "SKU-CHAIR") is None:
            set_stock(seed_session, "SKU-CHAIR", 100)
    finally:
        seed_session.close()

    consumer = ReliableConsumer(
        service_name=SERVICE_NAME,
        amqp_url=AMQP_URL,
        queue_name="inventory-service-events",
        bindings=["order.created", "inventory.release", "inventory.commit"],
        handler=consume_event,
    )
    outbox = OutboxPublisher(
        service_name=SERVICE_NAME,
        session_factory=SessionLocal,
        outbox_model=OutboxEvent,
        amqp_url=AMQP_URL,
    )
    consumer_thread = threading.Thread(target=consumer.run_forever, daemon=True)
    outbox_thread = threading.Thread(target=outbox.run_forever, daemon=True)
    consumer_thread.start()
    outbox_thread.start()
    app.state.consumer = consumer
    app.state.outbox = outbox
    yield
    consumer.stop()
    outbox.stop()
    consumer_thread.join(timeout=5)
    outbox_thread.join(timeout=5)


app = FastAPI(
    title="ResilientCart Inventory Service",
    version="1.0.0",
    lifespan=lifespan,
)
configure_tracing(SERVICE_NAME, app)
instrument_fastapi(app, SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/stock/{item_id}", response_model=StockResponse)
def get_stock(item_id: str, session: Session = Depends(get_session)) -> InventoryItem:
    item = session.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.put("/stock/{item_id}", response_model=StockResponse)
def update_stock(
    item_id: str,
    payload: SetStockRequest,
    session: Session = Depends(get_session),
) -> InventoryItem:
    return set_stock(session, item_id, payload.quantity)
