"""Pool de conexões Postgres e helpers de consulta tipada."""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TypeVar

from psycopg import Connection
from psycopg.rows import class_row
from psycopg_pool import ConnectionPool

from .config import settings

T = TypeVar("T")

_pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=settings.database_pool_max,
    kwargs={"prepare_threshold": None},
    open=False,
)


def abrir() -> None:
    _pool.open()


def fechar() -> None:
    _pool.close()


@contextmanager
def transacao() -> Iterator[Connection]:
    with _pool.connection() as conn:
        yield conn


def listar(conn: Connection, modelo: type[T], sql: str, params: Sequence[object] = ()) -> list[T]:
    with conn.cursor(row_factory=class_row(modelo)) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def buscar(conn: Connection, modelo: type[T], sql: str, params: Sequence[object] = ()) -> T | None:
    with conn.cursor(row_factory=class_row(modelo)) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def executar(conn: Connection, sql: str, params: Sequence[object] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount
