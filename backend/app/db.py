"""Connection pool and tiny query helpers.

Connections run in autocommit mode: a single statement is its own transaction (which is what the
SQL functions book_slot / cancel_appointment rely on), and a handler that needs several statements to
succeed or fail together wraps them in `with conn.transaction():`. Nothing depends on when the
framework runs dependency clean-up code, so data is already committed when a response is sent.
"""
from typing import Any, Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def open_pool() -> None:
    global _pool
    _pool = ConnectionPool(
        config.DATABASE_URL,
        min_size=1,
        max_size=config.DB_POOL_MAX,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "options": f"-c timezone={config.DB_TIMEZONE}",
        },
        open=False,
    )
    _pool.open(wait=True, timeout=15)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[Any]:
    """FastAPI dependency: one pooled connection per request."""
    if _pool is None:
        raise RuntimeError("database pool is not open")
    with _pool.connection() as conn:
        yield conn


def one(conn: Any, sql: str, params: dict | None = None) -> dict | None:
    return conn.execute(sql, params or {}).fetchone()


def many(conn: Any, sql: str, params: dict | None = None) -> list[dict]:
    return conn.execute(sql, params or {}).fetchall()


def run(conn: Any, sql: str, params: dict | None = None) -> int:
    """Execute and return the number of rows affected."""
    return conn.execute(sql, params or {}).rowcount
