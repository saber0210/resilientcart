from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from opentelemetry.propagate import inject


def create_event(
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    trace_context: dict[str, str] = {}
    inject(trace_context)
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "aggregate_id": aggregate_id,
        "correlation_id": correlation_id or str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "trace_context": trace_context,
        "payload": payload,
    }
