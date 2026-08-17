from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.inventory_service.models import Base as InventoryBase
from app.inventory_service.models import InventoryItem, OutboxEvent as InventoryOutbox
from app.inventory_service.service import handle_domain_event as handle_inventory_event
from app.inventory_service.service import set_stock
from app.notification_service.models import Base as NotificationBase
from app.notification_service.models import Notification
from app.notification_service.service import handle_domain_event as handle_notification_event
from app.order_service.models import Base as OrderBase
from app.order_service.models import Order, OutboxEvent as OrderOutbox
from app.order_service.schemas import CreateOrderRequest
from app.order_service.service import create_order
from app.order_service.service import handle_domain_event as handle_order_event
from app.payment_service.models import Base as PaymentBase
from app.payment_service.models import OutboxEvent as PaymentOutbox
from app.payment_service.service import handle_domain_event as handle_payment_event


def _session(base):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _event(session, model, routing_key: str, order_id: str) -> dict:
    rows = session.scalars(select(model).where(model.routing_key == routing_key)).all()
    return next(row.payload for row in rows if row.payload["aggregate_id"] == order_id)


def _run_checkout(
    *,
    customer_id: str,
    idempotency_key: str,
    order_session,
    inventory_session,
    payment_session,
    notification_session,
) -> Order:
    order, _ = create_order(
        order_session,
        CreateOrderRequest(
            customer_id=customer_id,
            item_id="SKU-TEST",
            quantity=1,
            amount_cents=4999,
        ),
        idempotency_key,
    )
    created = _event(order_session, OrderOutbox, "order.created", order.id)
    handle_inventory_event(inventory_session, created)

    reserved = _event(inventory_session, InventoryOutbox, "inventory.reserved", order.id)
    handle_order_event(order_session, reserved)
    handle_payment_event(payment_session, reserved)

    payment_key = "payment.failed" if customer_id.endswith("-fail") else "payment.succeeded"
    payment_result = _event(payment_session, PaymentOutbox, payment_key, order.id)
    handle_order_event(order_session, payment_result)

    if payment_key == "payment.succeeded":
        inventory_result = _event(order_session, OrderOutbox, "inventory.commit", order.id)
        notification_event = _event(order_session, OrderOutbox, "order.completed", order.id)
    else:
        inventory_result = _event(order_session, OrderOutbox, "inventory.release", order.id)
        notification_event = _event(order_session, OrderOutbox, "order.failed", order.id)

    handle_inventory_event(inventory_session, inventory_result)
    handle_notification_event(notification_session, notification_event)
    order_session.refresh(order)
    return order


def test_success_and_compensation_paths(monkeypatch) -> None:
    monkeypatch.setenv("PAYMENT_DELAY_MS", "0")
    order_session = _session(OrderBase)
    inventory_session = _session(InventoryBase)
    payment_session = _session(PaymentBase)
    notification_session = _session(NotificationBase)
    set_stock(inventory_session, "SKU-TEST", 2)

    successful = _run_checkout(
        customer_id="customer-ok",
        idempotency_key="success-key",
        order_session=order_session,
        inventory_session=inventory_session,
        payment_session=payment_session,
        notification_session=notification_session,
    )
    failed = _run_checkout(
        customer_id="customer-fail",
        idempotency_key="failure-key",
        order_session=order_session,
        inventory_session=inventory_session,
        payment_session=payment_session,
        notification_session=notification_session,
    )

    stock = inventory_session.get(InventoryItem, "SKU-TEST")
    notifications = notification_session.scalars(select(Notification)).all()

    assert successful.status == "COMPLETED"
    assert failed.status == "PAYMENT_FAILED"
    assert stock is not None
    assert (stock.available, stock.reserved, stock.sold) == (1, 0, 1)
    assert {notification.kind for notification in notifications} == {
        "ORDER_CONFIRMED",
        "ORDER_FAILED",
    }
