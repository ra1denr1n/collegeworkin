"""Работа с RabbitMQ."""
import json
import os

import aio_pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://shop:shop@rabbitmq:5672/")
ORDERS_QUEUE = "orders.process"


async def connect():
    # connect_robust сам переподключается, если RabbitMQ перезапустился
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    # durable=True — очередь переживёт перезапуск RabbitMQ
    queue = await channel.declare_queue(ORDERS_QUEUE, durable=True)
    return connection, channel, queue


async def publish(channel, payload: dict):
    message = aio_pika.Message(
        body=json.dumps(payload).encode(),
        content_type="application/json",
        # PERSISTENT — сообщение записывается на диск
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(message, routing_key=ORDERS_QUEUE)
