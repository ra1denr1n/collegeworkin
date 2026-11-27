"""Consumer: забирает заказы из очереди и проводит оплату."""
import asyncio
import json
import os
import socket

import asyncpg
import mq

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@pgbouncer:6432/shop_rw")
PAYMENT_DELAY = float(os.getenv("PAYMENT_DELAY_SEC", "0.2"))
PREFETCH = int(os.getenv("CONSUMER_PREFETCH", "10"))
STATEMENT_CACHE = int(os.getenv("DB_STATEMENT_CACHE_SIZE", "100"))
NAME = socket.gethostname()
_tasks = set()   # ссылки на запущенные задачи


async def handle(db, message):
    # process(): успех — ack, исключение — сообщение вернётся в очередь
    async with message.process(requeue=True):
        order_id = json.loads(message.body)["order_id"]
        await asyncio.sleep(PAYMENT_DELAY)       # «медленная оплата»
        await db.execute(
            """UPDATE orders
               SET status = 'processed', processed_at = now()
               WHERE id = $1 AND status = 'pending'""",
            order_id,
        )
        print(f"[{NAME}] заказ {order_id} обработан", flush=True)


async def safe_handle(db, message):
    try:
        await handle(db, message)
    except Exception as e:
        print(f"[{NAME}] ошибка: {e!r}", flush=True)


async def main():
    db = await asyncpg.create_pool(
        DATABASE_URL, min_size=1, max_size=PREFETCH, statement_cache_size=STATEMENT_CACHE,
    )
    connection, channel, queue = await mq.connect()
    await channel.set_qos(prefetch_count=PREFETCH)
    print(f"[{NAME}] жду сообщения...", flush=True)

    async with queue.iterator() as it:
        async for message in it:
            # Каждое сообщение — в отдельной задаче, параллельно
            task = asyncio.create_task(safe_handle(db, message))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)


if __name__ == "__main__":
    asyncio.run(main())
