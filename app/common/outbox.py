from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.logging import configure_logging, log
from app.common.messaging import RabbitPublisher
from app.common.metrics import OUTBOX_FAILURES, OUTBOX_PUBLISHED


class OutboxPublisher:
    def __init__(
        self,
        *,
        service_name: str,
        session_factory: Callable[[], Session],
        outbox_model: type[Any],
        amqp_url: str,
        poll_interval: float = 0.5,
        batch_size: int = 25,
    ) -> None:
        self.service_name = service_name
        self.session_factory = session_factory
        self.outbox_model = outbox_model
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.publisher = RabbitPublisher(amqp_url)
        self.stop_event = threading.Event()
        self.logger = configure_logging(service_name)

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            published = self.publish_batch()
            if published == 0:
                self.stop_event.wait(self.poll_interval)

    def publish_batch(self) -> int:
        session = self.session_factory()
        try:
            rows = (
                session.execute(
                    select(self.outbox_model)
                    .where(self.outbox_model.published_at.is_(None))
                    .order_by(self.outbox_model.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(self.batch_size)
                )
                .scalars()
                .all()
            )
            for row in rows:
                self.publisher.publish(row.routing_key, row.payload)
                row.published_at = datetime.now(UTC)
                row.attempts += 1
                OUTBOX_PUBLISHED.labels(
                    self.service_name,
                    row.payload.get("event_type", row.routing_key),
                ).inc()
            session.commit()
            return len(rows)
        except Exception as exc:
            session.rollback()
            OUTBOX_FAILURES.labels(self.service_name).inc()
            log(self.logger, "outbox_publish_failed", error=str(exc))
            return 0
        finally:
            session.close()

    def stop(self) -> None:
        self.stop_event.set()
        self.publisher.close()
