from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.common.events import create_event
from app.common.logging import configure_logging, log
from app.inventory_service.logic import can_reserve
from app.inventory_service.models import (
    InventoryItem,
    OutboxEvent,
    ProcessedEvent,
    Reservation,
)

logger = configure_logging("inventory-service")


def _add_outbox(session: Session, routing_key: str, event: dict[str, Any]) -> None:
    session.add(
        OutboxEvent(
            id=str(uuid4()),
            routing_key=routing_key,
            payload=event,
        )
    )


def set_stock(session: Session, item_id: str, quantity: int) -> InventoryItem:
    item = session.execute(
        select(InventoryItem)
        .where(InventoryItem.item_id == item_id)
        .with_for_update()
    ).scalar_one_or_none()
    if item is None:
        item = InventoryItem(item_id=item_id, available=quantity, reserved=0, sold=0)
        session.add(item)
    else:
        item.available = quantity
        item.reserved = 0
        item.sold = 0
        session.execute(delete(Reservation).where(Reservation.item_id == item_id))
    session.commit()
    session.refresh(item)
    return item


def handle_domain_event(session: Session, event: dict[str, Any]) -> None:
    event_id = str(event["event_id"])
    if session.get(ProcessedEvent, event_id):
        return

    event_type = str(event["event_type"])
    payload = event.get("payload", {})
    order_id = str(payload.get("order_id") or event["aggregate_id"])
    correlation_id = str(event.get("correlation_id", ""))

    if event_type == "order.created":
        existing = session.get(Reservation, order_id)
        if existing is None:
            item_id = str(payload["item_id"])
            quantity = int(payload["quantity"])
            item = session.execute(
                select(InventoryItem)
                .where(InventoryItem.item_id == item_id)
                .with_for_update()
            ).scalar_one_or_none()

            if item is not None and can_reserve(item.available, quantity):
                item.available -= quantity
                item.reserved += quantity
                session.add(
                    Reservation(
                        order_id=order_id,
                        item_id=item_id,
                        quantity=quantity,
                        status="RESERVED",
                    )
                )
                reserved = create_event(
                    "inventory.reserved",
                    order_id,
                    {
                        **payload,
                        "reservation_status": "RESERVED",
                    },
                    correlation_id=correlation_id,
                )
                _add_outbox(session, "inventory.reserved", reserved)
            else:
                reason = "item_not_found" if item is None else "insufficient_stock"
                rejected = create_event(
                    "inventory.rejected",
                    order_id,
                    {
                        **payload,
                        "reason": reason,
                    },
                    correlation_id=correlation_id,
                )
                _add_outbox(session, "inventory.rejected", rejected)

    elif event_type in {"inventory.release", "inventory.commit"}:
        reservation = session.execute(
            select(Reservation)
            .where(Reservation.order_id == order_id)
            .with_for_update()
        ).scalar_one_or_none()
        if reservation is not None and reservation.status == "RESERVED":
            item = session.execute(
                select(InventoryItem)
                .where(InventoryItem.item_id == reservation.item_id)
                .with_for_update()
            ).scalar_one()
            item.reserved -= reservation.quantity
            if event_type == "inventory.release":
                item.available += reservation.quantity
                reservation.status = "RELEASED"
                outcome_type = "inventory.released"
            else:
                item.sold += reservation.quantity
                reservation.status = "COMMITTED"
                outcome_type = "inventory.committed"
            outcome = create_event(
                outcome_type,
                order_id,
                {
                    "order_id": order_id,
                    "item_id": reservation.item_id,
                    "quantity": reservation.quantity,
                },
                correlation_id=correlation_id,
            )
            _add_outbox(session, outcome_type, outcome)

    session.add(ProcessedEvent(event_id=event_id))
    session.commit()
    log(
        logger,
        "inventory_event_processed",
        order_id=order_id,
        event_type=event_type,
        correlation_id=correlation_id,
    )
