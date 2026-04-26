from __future__ import annotations

from pathlib import Path

import pytest

from py_timetable import db


class _SimpleCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.conn.executed.append((query, params))

    def executemany(self, query, seq):
        self.conn.executed.append((query, list(seq)))

    def fetchone(self):
        return {"ok": 1}

    def fetchall(self):
        return [{"ok": 1}, {"ok": 2}]


class _SimpleConn:
    def __init__(self):
        self.executed = []
        self.autocommit = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return _SimpleCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_connect_uses_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_connect(url):
        captured["url"] = url
        return _SimpleConn()

    monkeypatch.setattr(db, "get_database_url", lambda: "postgresql://user:pw@localhost:5432/db")
    monkeypatch.setattr(db.psycopg2, "connect", fake_connect)

    conn = db.connect()

    assert isinstance(conn, _SimpleConn)
    assert captured["url"].startswith("postgresql://")


def test_fetch_one_executes_query() -> None:
    conn = _SimpleConn()

    row = db.fetch_one(conn, "SELECT 1 AS ok")

    assert row == {"ok": 1}
    assert conn.executed[0][0] == "SELECT 1 AS ok"


def test_transaction_commits_and_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _SimpleConn()
    monkeypatch.setattr(db, "connect", lambda: conn)

    with db.transaction() as opened:
        assert opened is conn

    assert conn.committed is True
    assert conn.closed is True


def test_transaction_rolls_back_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _SimpleConn()
    monkeypatch.setattr(db, "connect", lambda: conn)

    with pytest.raises(RuntimeError, match="boom"):
        with db.transaction():
            raise RuntimeError("boom")

    assert conn.rolled_back is True
    assert conn.closed is True


def test_run_sql_file_executes_file_contents(tmp_path: Path) -> None:
    conn = _SimpleConn()
    sql_path = tmp_path / "x.sql"
    sql_path.write_text("SELECT 42;", encoding="utf-8")

    db.run_sql_file(conn, sql_path)

    assert conn.executed[0][0] == "SELECT 42;"


def test_init_schema_raises_when_no_sql_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        db.init_schema(tmp_path)


def test_init_schema_runs_numbered_files_in_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "002_seed.sql").write_text("-- seed", encoding="utf-8")
    (tmp_path / "001_schema.sql").write_text("-- schema", encoding="utf-8")
    (tmp_path / "003_rooms_actual.sql").write_text("-- rooms", encoding="utf-8")

    conn = _SimpleConn()
    applied: list[str] = []

    @db.contextmanager
    def fake_transaction():
        yield conn

    def fake_run_sql_file(_conn, path: Path) -> None:
        applied.append(path.name)

    monkeypatch.setattr(db, "transaction", fake_transaction)
    monkeypatch.setattr(db, "run_sql_file", fake_run_sql_file)

    db.init_schema(tmp_path)

    assert applied == ["001_schema.sql", "002_seed.sql", "003_rooms_actual.sql"]


def test_fetch_all_execute_and_executemany_paths() -> None:
    conn = _SimpleConn()

    rows = db.fetch_all(conn, "SELECT 1", None)
    db.execute(conn, "UPDATE x SET y=%s", (1,))
    db.executemany(conn, "INSERT INTO x VALUES (%s)", [(1,), (2,)])

    assert len(rows) == 2
    assert any("UPDATE x SET y=%s" == q for q, _ in conn.executed)
    assert any("INSERT INTO x VALUES (%s)" == q for q, _ in conn.executed)
