from app.common.events import create_event


def test_event_envelope_contains_required_fields() -> None:
    event = create_event("order.created", "order-1", {"quantity": 1})

    assert event["event_type"] == "order.created"
    assert event["aggregate_id"] == "order-1"
    assert event["event_id"]
    assert event["correlation_id"]
    assert event["occurred_at"]
    assert event["payload"] == {"quantity": 1}
