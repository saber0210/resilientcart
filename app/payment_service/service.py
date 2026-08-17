from __future__ import annotations

import os
import time
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.common.events import create_event
from app.common.logging import configure_logging, log
from app.payment_service.models import OutboxEvent, Payment, ProcessedEvent

logger = configure_logging("payment-service")


def _add_outbox(session: Session, routing_key: str, event: dict[str, Any]) -> None:
    session.add(
        OutboxEvent(
            id=str(uuid4()),
            routing_key=routing_key,
            payload=event,
        )
    )


def should_fail_payment(customer_id: str, amount_cents: int) -> bool:
    return customer_id.lower().endswith("-fail") or amount_cents <= 0


def handle_domain_event(session: Session, event: dict[str, Any]) -> None:
    event_id = str(event["event_id"])
    if session.get(ProcessedEvent, event_id):
        return

    payload = event.get("payload", {})
    order_id = str(payload.get("order_id") or event["aggregate_id"])
    existing = session.get(Payment, order_id)
    if existing is not None:
        session.add(ProcessedEvent(event_id=event_id))
        session.commit()
        return

    delay_ms = int(os.getenv("PAYMENT_DELAY_MS", "150"))
    if delay_ms > 0:
        time.sleep(delay_ms / 1000)

    customer_id = str(payload["customer_id"])
    amount_cents = int(payload["amount_cents"])
    correlation_id = str(event.get("correlation_id", ""))
    failed = should_fail_payment(customer_id, amount_cents)

    if failed:
        payment = Payment(
            order_id=order_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            status="FAILED",
            provider_reference=None,
            failure_reason="simulated_provider_decline",
        )
        result = create_event(
            "payment.failed",
            order_id,
            {
                **payload,
                "reason": "simulated_provider_decline",
            },
            correlation_id=correlation_id,
        )
        routing_key = "payment.failed"
    else:
        provider_reference = f"pay_{uuid4().hex[:16]}"
        payment = Payment(
            order_id=order_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            status="SUCCEEDED",
            provider_reference=provider_reference,
            failure_reason=None,
        )
        result = create_event(
            "payment.succeeded",
            order_id,
            {
                **payload,
                "provider_reference": provider_reference,
            },
            correlation_id=correlation_id,
        )
        routing_key = "payment.succeeded"

    session.add(payment)
    session.add(ProcessedEvent(event_id=event_id))
    _add_outbox(session, routing_key, result)
    session.commit()
    log(
        logger,
        "payment_processed",
        order_id=order_id,
        status=payment.status,
        correlation_id=correlation_id,
    )
