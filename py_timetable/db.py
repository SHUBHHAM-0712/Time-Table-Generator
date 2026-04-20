from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, Mapping, Sequence

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from .envutil import get_database_url


def connect() -> PgConnection:
    return psycopg2.connect(get_database_url())


@contextmanager
def transaction() -> Generator[PgConnection, None, None]:
    conn = connect()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_sql_file(conn: PgConnection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def init_schema(sql_dir: Path) -> None:
    """Apply numbered SQL files (###_*.sql) in lexicographic order."""
    files = sorted(sql_dir.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise FileNotFoundError(f"No ###_*.sql files in {sql_dir}")
    with transaction() as conn:
        for f in files:
            run_sql_file(conn, f)


def fetch_all(conn: PgConnection, query: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def fetch_one(conn: PgConnection, query: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchone()


def execute(conn: PgConnection, query: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(query, params)


def executemany(conn: PgConnection, query: str, seq: Iterable[Sequence[Any]]) -> None:
    with conn.cursor() as cur:
        cur.executemany(query, seq)
