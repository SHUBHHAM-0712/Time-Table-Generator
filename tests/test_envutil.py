from __future__ import annotations

import pytest

from py_timetable import envutil


def test_get_database_url_from_primary_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(envutil, "load_env", lambda: None)
    monkeypatch.setattr(envutil.os, "getenv", lambda k: "postgresql://u:p@h:5432/db" if k == "DATABASE_URL" else None)

    url = envutil.get_database_url()

    assert url == "postgresql://u:p@h:5432/db"


def test_get_database_url_from_fallback_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(envutil, "load_env", lambda: None)

    def fake_getenv(key: str):
        if key == "DATABASE_URL":
            return None
        if key == "DATABSE_URL":
            return "'postgresql://u:p@h:5432/db'"
        return None

    monkeypatch.setattr(envutil.os, "getenv", fake_getenv)

    url = envutil.get_database_url()

    assert url == "postgresql://u:p@h:5432/db"


def test_get_database_url_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(envutil, "load_env", lambda: None)
    monkeypatch.setattr(envutil.os, "getenv", lambda _k: None)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        envutil.get_database_url()
