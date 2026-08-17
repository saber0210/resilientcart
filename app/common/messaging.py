from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from typing import Any

import pika
from opentelemetry import propagate, trace

from app.common.logging import configure_logging, log
from app.common.metrics import EVENTS_PROCESSED

EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "domain.events")
DEAD_LETTER_EXCHANGE = os.getenv("DEAD_LETTER_EXCHANGE", "domain.events.dlx")


def _connect(amqp_url: str, attempts: int = 30) -> pika.BlockingConnection:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return pika.BlockingConnection(pika.URLParameters(amqp_url))
        except pika.exceptions.AMQPError as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError("RabbitMQ did not become ready") from last_error


class RabbitPublisher:
    def __init__(self, amqp_url: str) -> None:
        self.amqp_url = amqp_url
        self.connection: pika.BlockingConnection | None = None
        self.channel: pika.adapters.blocking_connection.BlockingChannel | None = None

    def _ensure_connection(self) -> None:
        if self.connection and self.connection.is_open and self.channel and self.channel.is_open:
            return
        self.connection = _connect(self.amqp_url)
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        self.channel.confirm_delivery()

    def publish(self, routing_key: str, event: dict[str, Any]) -> None:
        self._ensure_connection()
        assert self.channel is not None
        body = json.dumps(event, separators=(",", ":"), default=str)
        try:
            self.channel.basic_publish(
                exchange=EVENT_EXCHANGE,
                routing_key=routing_key,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type="application/json",
                    type=event.get("event_type", routing_key),
                    message_id=event.get("event_id"),
                    correlation_id=event.get("correlation_id"),
                ),
                mandatory=False,
            )
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.connection and self.connection.is_open:
            self.connection.close()
        self.connection = None
        self.channel = None


class ReliableConsumer:
    def __init__(
        self,
        *,
        service_name: str,
        amqp_url: str,
        queue_name: str,
        bindings: list[str],
        handler: Callable[[dict[str, Any]], None],
        max_retries: int = 3,
        retry_delay_ms: int = 5_000,
    ) -> None:
        self.service_name = service_name
        self.amqp_url = amqp_url
        self.queue_name = queue_name
        self.bindings = bindings
        self.handler = handler
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.stop_event = threading.Event()
        self.connection: pika.BlockingConnection | None = None
        self.channel: pika.adapters.blocking_connection.BlockingChannel | None = None
        self.logger = configure_logging(service_name)
        self.tracer = trace.get_tracer(service_name)

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._consume()
            except Exception as exc:
                log(self.logger, "consumer_connection_failed", error=str(exc))
                if not self.stop_event.wait(2):
                    continue

    def _consume(self) -> None:
        self.connection = _connect(self.amqp_url)
        self.channel = self.connection.channel()
        self._declare_topology(self.channel)
        self.channel.basic_qos(prefetch_count=10)
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self._on_message,
            auto_ack=False,
        )
        log(
            self.logger,
            "consumer_started",
            queue=self.queue_name,
            bindings=self.bindings,
        )
        self.channel.start_consuming()

    def _declare_topology(
        self,
        channel: pika.adapters.blocking_connection.BlockingChannel,
    ) -> None:
        retry_exchange = f"{self.queue_name}.retry.exchange"
        retry_queue = f"{self.queue_name}.retry"
        dlq_name = f"{self.queue_name}.dlq"
        dlq_routing_key = f"{self.queue_name}.dlq"

        channel.exchange_declare(EVENT_EXCHANGE, exchange_type="topic", durable=True)
        channel.exchange_declare(retry_exchange, exchange_type="direct", durable=True)
        channel.exchange_declare(
            DEAD_LETTER_EXCHANGE,
            exchange_type="direct",
            durable=True,
        )

        channel.queue_declare(
            queue=self.queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": retry_exchange,
                "x-dead-letter-routing-key": retry_queue,
            },
        )
        for binding in self.bindings:
            channel.queue_bind(
                queue=self.queue_name,
                exchange=EVENT_EXCHANGE,
                routing_key=binding,
            )

        channel.queue_declare(
            queue=retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": self.retry_delay_ms,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": self.queue_name,
            },
        )
        channel.queue_bind(
            queue=retry_queue,
            exchange=retry_exchange,
            routing_key=retry_queue,
        )

        channel.queue_declare(queue=dlq_name, durable=True)
        channel.queue_bind(
            queue=dlq_name,
            exchange=DEAD_LETTER_EXCHANGE,
            routing_key=dlq_routing_key,
        )

    def _retry_count(self, headers: dict[str, Any]) -> int:
        deaths = headers.get("x-death", []) or []
        return sum(
            int(death.get("count", 0))
            for death in deaths
            if death.get("queue") == self.queue_name and death.get("reason") == "rejected"
        )

    def _on_message(
        self,
        channel: pika.adapters.blocking_connection.BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        event_type = "unknown"
        try:
            event = json.loads(body)
            event_type = str(event.get("event_type", "unknown"))
            context = propagate.extract(event.get("trace_context", {}))
            with self.tracer.start_as_current_span(
                f"consume {event_type}",
                context=context,
            ) as span:
                span.set_attribute("messaging.system", "rabbitmq")
                span.set_attribute("messaging.destination", self.queue_name)
                span.set_attribute("messaging.message.id", event.get("event_id", ""))
                self.handler(event)
            EVENTS_PROCESSED.labels(self.service_name, event_type, "success").inc()
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            EVENTS_PROCESSED.labels(self.service_name, event_type, "failure").inc()
            headers = properties.headers or {}
            retry_count = self._retry_count(headers)
            log(
                self.logger,
                "event_processing_failed",
                event_type=event_type,
                retry_count=retry_count,
                error=str(exc),
            )
            if retry_count >= self.max_retries:
                dlq_routing_key = f"{self.queue_name}.dlq"
                channel.basic_publish(
                    exchange=DEAD_LETTER_EXCHANGE,
                    routing_key=dlq_routing_key,
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=pika.DeliveryMode.Persistent,
                        content_type=properties.content_type or "application/json",
                        message_id=properties.message_id,
                        correlation_id=properties.correlation_id,
                        headers={**headers, "final-error": str(exc)},
                    ),
                )
                channel.basic_ack(delivery_tag=method.delivery_tag)
            else:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def stop(self) -> None:
        self.stop_event.set()
        if self.connection and self.connection.is_open and self.channel:
            self.connection.add_callback_threadsafe(self.channel.stop_consuming)
