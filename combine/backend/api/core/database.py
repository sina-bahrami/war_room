from __future__ import annotations

import asyncpg

from api.core.config import settings


class Database:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                settings.db_dsn,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )

    async def disconnect(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None


db = Database()
