"""Пул записи (primary) и пулы чтения (реплики)."""
import itertools
import os

import asyncpg

WRITE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@pg-primary:5432/shop")
# Список реплик через запятую; если не задан — читаем с primary
READ_URLS = [u.strip() for u in os.getenv("DATABASE_READ_URLS", WRITE_URL).split(",") if u.strip()]
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
# Понадобится в лабораторной 7 (PgBouncer)
STATEMENT_CACHE = int(os.getenv("DB_STATEMENT_CACHE_SIZE", "100"))


class Database:
    async def connect(self):
        self.write = await self._pool(WRITE_URL)
        self.reads = [await self._pool(u) for u in READ_URLS]
        self._rr = itertools.cycle(self.reads)   # по кругу

    async def _pool(self, url):
        return await asyncpg.create_pool(
            url, min_size=1, max_size=POOL_MAX, statement_cache_size=STATEMENT_CACHE,
        )

    @property
    def read(self):
        """Следующая реплика по кругу."""
        return next(self._rr)

    async def close(self):
        await self.write.close()
        for p in self.reads:
            await p.close()
