from __future__ import annotations

import os
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.common.metrics import instrument_fastapi
from app.common.telemetry import configure_tracing

SERVICE_NAME = "api-gateway"
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8000")
INVENTORY_SERVICE_URL = os.getenv(
    "INVENTORY_SERVICE_URL", "http://inventory-service:8000"
)
NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL", "http://notification-service:8000"
)

app = FastAPI(title="ResilientCart API Gateway", version="1.0.0")
configure_tracing(SERVICE_NAME, app)
instrument_fastapi(app, SERVICE_NAME)


class CheckoutRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=128)
    item_id: str = Field(default="SKU-CHAIR", min_length=1, max_length=128)
    quantity: int = Field(default=1, ge=1, le=100)
    amount_cents: int = Field(default=4999, ge=1, le=100_000_000)


class SetStockRequest(BaseModel):
    quantity: int = Field(ge=0, le=1_000_000)


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.request(method, url, **kwargs)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Downstream service unavailable: {exc}",
        ) from exc


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def demo_page() -> str:
    return DEMO_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/api/checkout")
async def checkout(
    payload: CheckoutRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = idempotency_key or str(uuid4())
    upstream = await _request(
        "POST",
        f"{ORDER_SERVICE_URL}/orders",
        json=payload.model_dump(),
        headers={"Idempotency-Key": key},
    )
    response.status_code = upstream.status_code
    response.headers["Idempotency-Key"] = key
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)
    return upstream.json()


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    upstream = await _request("GET", f"{ORDER_SERVICE_URL}/orders/{order_id}")
    if upstream.status_code == 404:
        raise HTTPException(status_code=404, detail="Order not found")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)
    return upstream.json()


@app.get("/api/inventory/{item_id}")
async def get_inventory(item_id: str):
    upstream = await _request("GET", f"{INVENTORY_SERVICE_URL}/stock/{item_id}")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)
    return upstream.json()


@app.put("/api/inventory/{item_id}")
async def set_inventory(item_id: str, payload: SetStockRequest):
    upstream = await _request(
        "PUT",
        f"{INVENTORY_SERVICE_URL}/stock/{item_id}",
        json=payload.model_dump(),
    )
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)
    return upstream.json()


@app.get("/api/notifications")
async def notifications(limit: int = 20):
    upstream = await _request(
        "GET",
        f"{NOTIFICATION_SERVICE_URL}/notifications",
        params={"limit": min(max(limit, 1), 100)},
    )
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)
    return upstream.json()


DEMO_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ResilientCart</title>
  <style>
    :root { color-scheme: dark; --bg:#07111f; --card:#0f1c2e; --line:#21344d; --text:#eff6ff; --muted:#9fb0c5; --accent:#7dd3fc; --good:#86efac; --bad:#fca5a5; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:Inter,ui-sans-serif,system-ui,sans-serif; background:radial-gradient(circle at top right,#12315a 0,var(--bg) 42%); color:var(--text); min-height:100vh; }
    main { width:min(1080px,92vw); margin:0 auto; padding:52px 0 80px; }
    .eyebrow { color:var(--accent); font-weight:700; letter-spacing:.14em; text-transform:uppercase; font-size:.78rem; }
    h1 { font-size:clamp(2.5rem,7vw,5.6rem); line-height:.94; margin:.55rem 0 1rem; max-width:850px; }
    .lead { color:var(--muted); font-size:1.08rem; line-height:1.7; max-width:760px; }
    .grid { display:grid; grid-template-columns:1.05fr .95fr; gap:20px; margin-top:34px; }
    .card { background:rgba(15,28,46,.88); border:1px solid var(--line); border-radius:20px; padding:24px; box-shadow:0 18px 60px rgba(0,0,0,.25); backdrop-filter:blur(12px); }
    h2 { margin:0 0 18px; font-size:1.2rem; }
    label { display:block; color:var(--muted); font-size:.82rem; margin:14px 0 6px; }
    input { width:100%; border:1px solid var(--line); border-radius:11px; padding:12px 13px; background:#081525; color:var(--text); font-size:.96rem; }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    button { border:0; border-radius:12px; padding:13px 17px; font-weight:800; cursor:pointer; margin-top:18px; background:var(--accent); color:#062033; }
    button.secondary { background:#1e334d; color:var(--text); margin-left:8px; }
    pre { white-space:pre-wrap; word-break:break-word; background:#07111f; border:1px solid var(--line); border-radius:12px; padding:16px; min-height:250px; color:#cfe7ff; line-height:1.55; overflow:auto; }
    .flow { display:flex; flex-wrap:wrap; gap:8px; margin-top:24px; }
    .pill { border:1px solid var(--line); border-radius:999px; padding:8px 11px; color:var(--muted); font-size:.78rem; }
    .links { margin-top:16px; color:var(--muted); font-size:.88rem; }
    .links a { color:var(--accent); margin-right:14px; }
    @media (max-width:800px) { .grid { grid-template-columns:1fr; } .row { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main>
  <div class="eyebrow">Event-driven system design portfolio</div>
  <h1>Checkout that survives partial failure.</h1>
  <p class="lead">ResilientCart demonstrates Saga orchestration, transactional outboxes, idempotent consumers, row-level inventory locking, delayed retries, dead-letter queues, traces, metrics, and compensating transactions.</p>
  <div class="flow">
    <span class="pill">API Gateway</span><span class="pill">Order Service</span><span class="pill">RabbitMQ</span><span class="pill">Inventory Service</span><span class="pill">Payment Service</span><span class="pill">Notification Service</span>
  </div>
  <div class="grid">
    <section class="card">
      <h2>Run a checkout</h2>
      <label>Customer ID <small>(end with <code>-fail</code> to simulate decline)</small></label>
      <input id="customer" value="graduate-demo" />
      <label>Item ID</label>
      <input id="item" value="SKU-CHAIR" />
      <div class="row">
        <div><label>Quantity</label><input id="quantity" type="number" min="1" value="1" /></div>
        <div><label>Amount, cents</label><input id="amount" type="number" min="1" value="4999" /></div>
      </div>
      <button onclick="checkout()">Create order</button>
      <button class="secondary" onclick="resetStock()">Reset stock to 100</button>
      <div class="links"><a href="/docs">OpenAPI</a><a href="http://localhost:16686">Jaeger</a><a href="http://localhost:3000">Grafana</a><a href="http://localhost:15672">RabbitMQ</a></div>
    </section>
    <section class="card">
      <h2>Live order state</h2>
      <pre id="output">Ready. Submit a successful order or use a customer ID ending in “-fail” to watch the compensation path.</pre>
    </section>
  </div>
</main>
<script>
const output = document.getElementById('output');
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function checkout() {
  output.textContent = 'Creating order...';
  const body = {
    customer_id: document.getElementById('customer').value,
    item_id: document.getElementById('item').value,
    quantity: Number(document.getElementById('quantity').value),
    amount_cents: Number(document.getElementById('amount').value)
  };
  const key = crypto.randomUUID();
  const res = await fetch('/api/checkout', {method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key':key}, body:JSON.stringify(body)});
  const order = await res.json();
  output.textContent = JSON.stringify(order, null, 2);
  if (!order.id) return;
  for (let i=0; i<30; i++) {
    await sleep(650);
    const current = await (await fetch('/api/orders/' + order.id)).json();
    output.textContent = JSON.stringify(current, null, 2);
    if (['COMPLETED','REJECTED','PAYMENT_FAILED'].includes(current.status)) break;
  }
}
async function resetStock() {
  const item = document.getElementById('item').value;
  const res = await fetch('/api/inventory/' + encodeURIComponent(item), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({quantity:100})});
  output.textContent = JSON.stringify(await res.json(), null, 2);
}
</script>
</body>
</html>"""
