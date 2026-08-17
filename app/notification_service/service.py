from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.logging import configure_logging, log
from app.notification_service.models import Notification

logger = configure_logging("notification-service")


def handle_domain_event(session: Session, event: dict) -> None:
    event_id = str(event["event_id"])
    if session.get(Notification, event_id):
        return

    payload = event.get("payload", {})
    event_type = str(event["event_type"])
    order_id = str(payload.get("order_id") or event["aggregate_id"])
    customer_id = str(payload.get("customer_id", "unknown"))

    if event_type == "order.completed":
        kind = "ORDER_CONFIRMED"
        message = f"Order {order_id} was completed successfully."
    else:
        kind = "ORDER_FAILED"
        message = f"Order {order_id} failed: {payload.get('reason', 'unknown_reason')}."

    notification = Notification(
        event_id=event_id,
        order_id=order_id,
        customer_id=customer_id,
        kind=kind,
        message=message,
    )
    session.add(notification)
    session.commit()
    log(
        logger,
        "notification_recorded",
        order_id=order_id,
        kind=kind,
        correlation_id=event.get("correlation_id"),
    )
