from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from app.common.messaging import ReliableConsumer
from app.common.metrics import instrument_fastapi
from app.common.telemetry import configure_tracing
from app.notification_service.models import Base, Notification
from app.notification_service.schemas import NotificationResponse
from app.notification_service.service import handle_domain_event

SERVICE_NAME = "notification-service"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@postgres:5432/notificationdb",
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
        queue_name="notification-service-events",
        bindings=["order.completed", "order.failed"],
        handler=consume_event,
    )
    consumer_thread = threading.Thread(target=consumer.run_forever, daemon=True)
    consumer_thread.start()
    app.state.consumer = consumer
    yield
    consumer.stop()
    consumer_thread.join(timeout=5)


app = FastAPI(
    title="ResilientCart Notification Service",
    version="1.0.0",
    lifespan=lifespan,
)
configure_tracing(SERVICE_NAME, app)
instrument_fastapi(app, SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[Notification]:
    return list(
        session.scalars(
            select(Notification).order_by(Notification.created_at.desc()).limit(limit)
        )
    )
