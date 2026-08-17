from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "resilientcart_http_requests_total",
    "HTTP requests processed by ResilientCart services",
    ["service", "method", "path", "status"],
)
HTTP_DURATION = Histogram(
    "resilientcart_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
)
EVENTS_PROCESSED = Counter(
    "resilientcart_events_processed_total",
    "Domain events processed",
    ["service", "event_type", "result"],
)
OUTBOX_PUBLISHED = Counter(
    "resilientcart_outbox_published_total",
    "Outbox events successfully published",
    ["service", "event_type"],
)
OUTBOX_FAILURES = Counter(
    "resilientcart_outbox_publish_failures_total",
    "Outbox publication failures",
    ["service"],
)


def instrument_fastapi(app: FastAPI, service_name: str) -> None:
    @app.middleware("http")
    async def metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            HTTP_REQUESTS.labels(service_name, request.method, path, "500").inc()
            HTTP_DURATION.labels(service_name, request.method, path).observe(
                time.perf_counter() - started
            )
            raise

        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(
            service_name,
            request.method,
            path,
            str(response.status_code),
        ).inc()
        HTTP_DURATION.labels(service_name, request.method, path).observe(
            time.perf_counter() - started
        )
        return response

    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.add_api_route("/metrics", metrics, include_in_schema=False)
