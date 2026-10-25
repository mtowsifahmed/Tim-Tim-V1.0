import asyncpg

from .config import settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    # statement_cache_size=0 keeps this compatible with Supabase's pgbouncer pooler.
    _pool = await asyncpg.create_pool(settings.supabase_db_url, min_size=1, max_size=8,
                                      statement_cache_size=0)
    return _pool


def pool() -> asyncpg.Pool:
    assert _pool is not None, "DB pool not initialised"
    return _pool


async def close_pool() -> None:
    if _pool:
        await _pool.close()
