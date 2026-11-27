"""
Мини-магазин: FastAPI + PostgreSQL (primary + replicas) + Redis Cluster + RabbitMQ.
"""
import os
import socket
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from redis.asyncio.cluster import RedisCluster

from cache import Cache
from db import Database
import mq

# --- Настройки из переменных окружения ---
REDIS_URL = os.getenv("REDIS_URL", "redis://172.30.0.11:6379")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "1") == "1"
TTL_PRODUCT = 60
TTL_LIST = 30
TTL_TOP = 30

INSTANCE = os.getenv("INSTANCE_NAME") or socket.gethostname()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = Database()
    await app.state.db.connect()
    app.state.redis = RedisCluster.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.initialize()
    app.state.cache = Cache(app.state.redis, enabled=CACHE_ENABLED)
    app.state.mq_conn, app.state.mq_channel, _ = await mq.connect()
    yield
    await app.state.mq_conn.close()
    await app.state.redis.aclose()
    await app.state.db.close()


app = FastAPI(title="Мини-магазин", lifespan=lifespan)


REQUESTS = Counter(
    "app_requests_total", "Количество HTTP-запросов", ["method", "route", "status"]
)
LATENCY = Histogram(
    "app_request_duration_seconds",
    "Время обработки запроса",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
CACHE_RESULTS = Counter("app_cache_total", "Попадания и промахи кэша", ["result"])


@app.middleware("http")
async def metrics_and_instance(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    # Шаблон маршрута (/products/{product_id}), а не реальный путь —
    # иначе у метрики будут сотни тысяч вариантов меток
    route = request.scope.get("route")
    path = getattr(route, "path", "unknown")
    if path != "/metrics":
        LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
        REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        if "X-Cache" in response.headers:
            CACHE_RESULTS.labels(response.headers["X-Cache"].lower()).inc()
    response.headers["X-Instance"] = INSTANCE
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class OrderIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=100)


@app.get("/")
async def index():
    return {"service": "mini-shop", "instance": INSTANCE}


@app.get("/health")
async def health():
    await app.state.db.write.fetchval("SELECT 1")
    for pool in app.state.db.reads:
        await pool.fetchval("SELECT 1")
    await app.state.redis.ping()
    return {"status": "ok", "instance": INSTANCE}


@app.get("/admin/cache-node/{product_id}")
async def cache_node(product_id: int):
    """На каком узле кластера лежит ключ товара."""
    key = f"product:{product_id}"
    rc = app.state.redis
    node = rc.get_node_from_key(key)
    return {
        "key": key,
        "hash_slot": rc.keyslot(key),
        "node": f"{node.host}:{node.port}",
        "cached": await rc.exists(key) == 1,
    }


@app.get("/products/search")
async def search_products(q: str = Query(min_length=2, max_length=50),
                          limit: int = Query(20, ge=1, le=100)):
    rows = await app.state.db.read.fetch(
        "SELECT id, name, price FROM products WHERE name ILIKE $1 LIMIT $2",
        f"%{q}%", limit,
    )
    return [dict(r) for r in rows]


@app.get("/products")
async def list_products(response: Response,
                        category_id: int = Query(1, ge=1),
                        limit: int = Query(20, ge=1, le=100),
                        offset: int = Query(0, ge=0, le=10000)):
    """Товары категории, сначала самые дорогие."""
    key = f"products:cat:{category_id}:{limit}:{offset}"
    cached = await app.state.cache.get(key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    rows = await app.state.db.read.fetch(
        """SELECT id, name, price, stock FROM products
           WHERE category_id = $1
           ORDER BY price DESC
           LIMIT $2 OFFSET $3""",
        category_id, limit, offset,
    )
    data = [dict(r) for r in rows]
    await app.state.cache.set(key, data, TTL_LIST)
    response.headers["X-Cache"] = "MISS"
    return data


@app.get("/products/{product_id}")
async def get_product(product_id: int, response: Response):
    key = f"product:{product_id}"
    cached = await app.state.cache.get(key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    row = await app.state.db.read.fetchrow(
        """SELECT p.id, p.name, p.description, p.price, p.stock, c.name AS category
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.id = $1""",
        product_id,
    )
    if row is None:
        raise HTTPException(404, "Товар не найден")
    data = dict(row)
    await app.state.cache.set(key, data, TTL_PRODUCT)
    response.headers["X-Cache"] = "MISS"
    return data


@app.get("/stats/top-products")
async def top_products(response: Response):
    """Топ-10 продаваемых товаров за неделю — «тяжёлый» запрос."""
    key = "stats:top-products"
    cached = await app.state.cache.get(key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    rows = await app.state.db.read.fetch(
        """SELECT p.id, p.name, t.sold
           FROM (SELECT product_id, sum(quantity) AS sold
                 FROM orders
                 WHERE created_at > now() - interval '7 days'
                 GROUP BY product_id
                 ORDER BY sold DESC
                 LIMIT 10) t
           JOIN products p ON p.id = t.product_id
           ORDER BY t.sold DESC"""
    )
    data = [dict(r) for r in rows]
    await app.state.cache.set(key, data, TTL_TOP)
    response.headers["X-Cache"] = "MISS"
    return data


@app.post("/orders", status_code=202)
async def create_order(order: OrderIn):
    async with app.state.db.write.acquire() as conn:
        async with conn.transaction():
            product = await conn.fetchrow(
                "SELECT price, stock FROM products WHERE id = $1 FOR UPDATE",
                order.product_id,
            )
            if product is None:
                raise HTTPException(404, "Товар не найден")
            if product["stock"] < order.quantity:
                raise HTTPException(409, "Недостаточно товара на складе")

            await conn.execute(
                "UPDATE products SET stock = stock - $1 WHERE id = $2",
                order.quantity, order.product_id,
            )
            row = await conn.fetchrow(
                """INSERT INTO orders (product_id, quantity, total, status)
                   VALUES ($1, $2, $3, 'pending')
                   RETURNING id, product_id, quantity, total, status, created_at""",
                order.product_id, order.quantity, product["price"] * order.quantity,
            )
    await mq.publish(app.state.mq_channel, {"order_id": row["id"]})
    await app.state.cache.delete(f"product:{order.product_id}")
    return dict(row)


@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    row = await app.state.db.write.fetchrow(
        """SELECT id, product_id, quantity, total, status, created_at, processed_at
           FROM orders
           WHERE id = $1""",
        order_id,
    )
    if row is None:
        raise HTTPException(404, "Заказ не найден")
    return dict(row)


@app.get("/admin/replication")
async def replication_status():
    """Состояние репликации глазами primary."""
    rows = await app.state.db.write.fetch(
        """SELECT client_addr::text, state, sync_state,
                  pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes,
                  replay_lag::text
           FROM pg_stat_replication"""
    )
    return [dict(r) for r in rows]
