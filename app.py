import time
import uuid
import base64
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TOTAL_ORDERS = 49
RATE_LIMIT = 17
WINDOW = 10  # seconds

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# In-memory storage
# -----------------------------
orders_created = {}
client_requests = defaultdict(deque)


class OrderRequest(BaseModel):
    item: str = "default"


# -----------------------------------
# Rate Limiter
# -----------------------------------
def check_rate_limit(client_id: str, response: Response):
    now = time.time()

    bucket = client_requests[client_id]

    while bucket and bucket[0] <= now - WINDOW:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT:
        retry_after = int(WINDOW - (now - bucket[0])) + 1
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    bucket.append(now)


# -----------------------------------
# POST /orders
# -----------------------------------
@app.post("/orders", status_code=201)
def create_order(
    order: OrderRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_client_id: str = Header("default", alias="X-Client-Id"),
):
    check_rate_limit(x_client_id, response)

    if idempotency_key in orders_created:
        return orders_created[idempotency_key]

    new_order = {
        "id": str(uuid.uuid4()),
        "item": order.item,
    }

    orders_created[idempotency_key] = new_order

    return new_order


# -----------------------------------
# GET /orders
# -----------------------------------
@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: str | None = None,
    response: Response = None,
    x_client_id: str = Header("default", alias="X-Client-Id"),
):
    check_rate_limit(x_client_id, response)

    if cursor:
        start = int(base64.b64decode(cursor).decode())
    else:
        start = 1

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [{"id": i} for i in range(start, end + 1)]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(str(end + 1).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
