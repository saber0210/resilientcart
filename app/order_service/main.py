from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
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
from app.order_service.models import Base, Order, OutboxEvent
from app.order_service.schemas import CreateOrderRequest, OrderResponse
from app.order_service.service import create_order, handle_domain_event

SERVICE_NAME = "order-service"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@postgres:5432/orderdb",
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
    consumer = ReliableConsumer(
        service_name=SERVICE_NAME,
        amqp_url=AMQP_URL,
        queue_name="order-service-events",
        bindings=[
            "inventory.reserved",
            "inventory.rejected",
            "payment.succeeded",
            "payment.failed",
        ],
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
    title="ResilientCart Order Service",
    version="1.0.0",
    lifespan=lifespan,
)
configure_tracing(SERVICE_NAME, app)
instrument_fastapi(app, SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order_endpoint(
    payload: CreateOrderRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> Order:
    key = (idempotency_key or str(uuid4())).strip()
    if not key or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must contain 1 to 128 characters",
        )
    order, created = create_order(session, payload, key)
    response.headers["Idempotency-Key"] = key
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return order


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, session: Session = Depends(get_session)) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
