from __future__ import annotations

TERMINAL_STATUSES = {"COMPLETED", "REJECTED", "PAYMENT_FAILED"}

EVENT_TO_STATUS = {
    "inventory.reserved": "INVENTORY_RESERVED",
    "inventory.rejected": "REJECTED",
    "payment.succeeded": "COMPLETED",
    "payment.failed": "PAYMENT_FAILED",
}

ALLOWED_TRANSITIONS = {
    "PENDING": {"INVENTORY_RESERVED", "REJECTED", "COMPLETED", "PAYMENT_FAILED"},
    "INVENTORY_RESERVED": {"COMPLETED", "PAYMENT_FAILED"},
    "COMPLETED": set(),
    "REJECTED": set(),
    "PAYMENT_FAILED": set(),
}


def next_status(current_status: str, event_type: str) -> str:
    requested = EVENT_TO_STATUS.get(event_type)
    if requested is None:
        return current_status
    if requested == current_status:
        return current_status
    if requested not in ALLOWED_TRANSITIONS.get(current_status, set()):
        return current_status
    return requested
