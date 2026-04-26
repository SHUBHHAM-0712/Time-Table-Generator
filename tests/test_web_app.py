from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from py_timetable.web import app as web_app


class StubCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _query: str):
        return None


class StubConn:
    def __init__(self):
        self.closed = False
        self.committed = False

    def cursor(self):
        return StubCursor()

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_api_health_success(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "_conn", lambda: StubConn())
    client = TestClient(web_app.app)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_api_health_failure(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "_conn", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    client = TestClient(web_app.app)

    resp = client.get("/api/health")

    assert resp.status_code == 503
    assert resp.json()["ok"] is False


def test_api_meta_and_runs(monkeypatch) -> None:
    conn = StubConn()
    monkeypatch.setattr(web_app, "_conn", lambda: conn)
    monkeypatch.setattr(web_app.db, "fetch_one", lambda *_a, **_k: {"n": 2})
    monkeypatch.setattr(
        web_app.db,
        "fetch_all",
        lambda *_a, **_k: [{"run_id": 1, "label": "r1", "source_csv": "db", "status": "completed", "notes": "ok", "created_at": "x"}],
    )
    client = TestClient(web_app.app)

    meta = client.get("/api/meta")
    runs = client.get("/api/runs")

    assert meta.status_code == 200
    assert meta.json()["faculty"] == 2
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == 1


def test_api_schedule_success(monkeypatch) -> None:
    conn = StubConn()
    monkeypatch.setattr(web_app, "_conn", lambda: conn)
    monkeypatch.setattr(web_app, "run_scheduler", lambda *_a, **_k: (7, True, "ok"))
    client = TestClient(web_app.app)

    resp = client.post("/api/schedule", data={"label": "w", "source": "db", "timeout": 30, "term": "all"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["run_id"] == 7


def test_api_schedule_bad_term(monkeypatch) -> None:
    conn = StubConn()
    monkeypatch.setattr(web_app, "_conn", lambda: conn)

    def bad_term(*_a, **_k):
        raise ValueError("Unknown term")

    monkeypatch.setattr(web_app, "run_scheduler", bad_term)
    client = TestClient(web_app.app)

    resp = client.post("/api/schedule", data={"term": "zzz"})

    assert resp.status_code == 400


def test_api_load_without_files(monkeypatch) -> None:
    conn = StubConn()
    monkeypatch.setattr(web_app, "_conn", lambda: conn)
    client = TestClient(web_app.app)

    resp = client.post("/api/load")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_api_export_zip(monkeypatch, tmp_path: Path) -> None:
    conn = StubConn()
    monkeypatch.setattr(web_app, "_conn", lambda: conn)

    def fake_export_excel(_conn, _run_id, out_dir: Path):
        p = out_dir / "a.xlsx"
        p.write_text("x", encoding="utf-8")
        return [p]

    def fake_export_pdf(_conn, _run_id, out_dir: Path):
        p = out_dir / "a.pdf"
        p.write_text("x", encoding="utf-8")
        return p

    monkeypatch.setattr(web_app, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(web_app, "export_excel", fake_export_excel)
    monkeypatch.setattr(web_app, "export_pdf_summary", fake_export_pdf)

    client = TestClient(web_app.app)
    resp = client.get("/api/export/1/zip")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
