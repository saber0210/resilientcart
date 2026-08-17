from app.order_service.state_machine import next_status


def test_happy_path_transitions() -> None:
    assert next_status("PENDING", "inventory.reserved") == "INVENTORY_RESERVED"
    assert next_status("INVENTORY_RESERVED", "payment.succeeded") == "COMPLETED"


def test_failed_payment_is_terminal() -> None:
    assert next_status("INVENTORY_RESERVED", "payment.failed") == "PAYMENT_FAILED"
    assert next_status("PAYMENT_FAILED", "payment.succeeded") == "PAYMENT_FAILED"


def test_unknown_event_does_not_change_state() -> None:
    assert next_status("PENDING", "catalog.updated") == "PENDING"
