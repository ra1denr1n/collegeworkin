"""Кэш в Redis по схеме Cache-Aside."""
import json
from datetime import date, datetime
from decimal import Decimal


def _default(obj):
    # json не умеет сериализовать Decimal и datetime — помогаем ему
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Не могу сериализовать {type(obj)}")


class Cache:
    def __init__(self, client, enabled: bool = True):
        self.r = client
        self.enabled = enabled

    async def get(self, key: str):
        if not self.enabled:
            return None
        try:
            raw = await self.r.get(key)
        except Exception:
            return None            # Redis недоступен — работаем без кэша
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value, ttl: int):
        if not self.enabled:
            return
        try:
            await self.r.set(key, json.dumps(value, default=_default), ex=ttl)
        except Exception:
            pass

    async def delete(self, *keys: str):
        if not self.enabled:
            return
        try:
            for k in keys:         # по одному: важно для Redis Cluster (лабораторная 4)
                await self.r.delete(k)
        except Exception:
            pass
