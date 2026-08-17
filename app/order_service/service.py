from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.events import create_event
from app.common.logging import configure_logging, log
from app.order_service.models import Order, OutboxEvent, ProcessedEvent
from app.order_service.schemas import CreateOrderRequest
from app.order_service.state_machine import next_status

logger = configure_logging("order-service")


def _add_outbox(session: Session, routing_key: str, event: dict[str, Any]) -> None:
    session.add(
        OutboxEvent(
            id=str(uuid4()),
            routing_key=routing_key,
            payload=event,
        )
    )


def create_order(
    session: Session,
    request: CreateOrderRequest,
    idempotency_key: str,
) -> tuple[Order, bool]:
    existing = session.scalar(
        select(Order).where(Order.idempotency_key == idempotency_key)
    )
    if existing:
        return existing, False

    order_id = str(uuid4())
    correlation_id = str(uuid4())
    order = Order(
        id=order_id,
        idempotency_key=idempotency_key,
        customer_id=request.customer_id,
        item_id=request.item_id,
        quantity=request.quantity,
        amount_cents=request.amount_cents,
        status="PENDING",
        reason=None,
        correlation_id=correlation_id,
    )
    event = create_event(
        "order.created",
        order_id,
        {
            "order_id": order_id,
            "customer_id": request.customer_id,
            "item_id": request.item_id,
            "quantity": request.quantity,
            "amount_cents": request.amount_cents,
        },
        correlation_id=correlation_id,
    )
    session.add(order)
    _add_outbox(session, "order.created", event)
    try:
        session.commit()
        session.refresh(order)
        log(logger, "order_created", order_id=order.id, correlation_id=correlation_id)
        return order, True
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        if existing is None:
            raise
        return existing, False


def handle_domain_event(session: Session, event: dict[str, Any]) -> None:
    event_id = str(event["event_id"])
    if session.get(ProcessedEvent, event_id):
        return

    order_id = str(event["aggregate_id"])
    order = session.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order {order_id} does not exist")

    event_type = str(event["event_type"])
    old_status = order.status
    new_status = next_status(old_status, event_type)
    payload = event.get("payload", {})

    if new_status != old_status:
        order.status = new_status
        order.reason = payload.get("reason")

        if event_type == "payment.succeeded":
            commit_inventory = create_event(
                "inventory.commit",
                order.id,
                {
                    "order_id": order.id,
                    "item_id": order.item_id,
                    "quantity": order.quantity,
                },
                correlation_id=order.correlation_id,
            )
            _add_outbox(session, "inventory.commit", commit_inventory)
            completed = create_event(
                "order.completed",
                order.id,
                {
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "item_id": order.item_id,
                    "quantity": order.quantity,
                    "amount_cents": order.amount_cents,
                },
                correlation_id=order.correlation_id,
            )
            _add_outbox(session, "order.completed", completed)

        if event_type == "payment.failed":
            release = create_event(
                "inventory.release",
                order.id,
                {
                    "order_id": order.id,
                    "item_id": order.item_id,
                    "quantity": order.quantity,
                    "reason": payload.get("reason", "payment_failed"),
                },
                correlation_id=order.correlation_id,
            )
            failed = create_event(
                "order.failed",
                order.id,
                {
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "reason": payload.get("reason", "payment_failed"),
                },
                correlation_id=order.correlation_id,
            )
            _add_outbox(session, "inventory.release", release)
            _add_outbox(session, "order.failed", failed)

        if event_type == "inventory.rejected":
            failed = create_event(
                "order.failed",
                order.id,
                {
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "reason": payload.get("reason", "inventory_rejected"),
                },
                correlation_id=order.correlation_id,
            )
            _add_outbox(session, "order.failed", failed)

    session.add(ProcessedEvent(event_id=event_id))
    session.commit()
    log(
        logger,
        "order_state_updated",
        order_id=order.id,
        event_type=event_type,
        old_status=old_status,
        new_status=order.status,
        correlation_id=order.correlation_id,
    )
