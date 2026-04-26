from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from py_timetable import __main__ as cli


def test_cmd_init_db_calls_init_schema(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    called: dict[str, Path] = {}

    def fake_init_schema(path: Path) -> None:
        called["sql_dir"] = path

    monkeypatch.setattr(cli.db, "init_schema", fake_init_schema)

    rc = cli.cmd_init_db(Namespace())

    out = capsys.readouterr().out
    assert rc == 0
    assert "Applied SQL" in out
    assert called["sql_dir"].name == "sql"


def test_cmd_load_without_slots(monkeypatch: pytest.MonkeyPatch, fake_conn, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "_root", lambda: Path("F:/Time-Table-Generator"))
    monkeypatch.setattr(cli.db, "connect", lambda: fake_conn)
    monkeypatch.setattr(cli, "get_default_batch_size", lambda _conn: 60)
    monkeypatch.setattr(
        cli,
        "ingest_academic_csv",
        lambda _conn, _csv_path, _bs: {"rows": 2, "courses": 2, "skipped_zero_lecture": 1},
    )

    args = Namespace(csv="autumn.csv", slots=None)
    rc = cli.cmd_load(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert "Leaving time_matrix unchanged" in out
    assert fake_conn.committed is True
    assert fake_conn.closed is True


def test_cmd_schedule_value_error(monkeypatch: pytest.MonkeyPatch, fake_conn, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli.db, "connect", lambda: fake_conn)

    def raise_value_error(*_args, **_kwargs):
        raise ValueError("bad term")

    monkeypatch.setattr(cli, "run_scheduler", raise_value_error)

    args = Namespace(label="x", source="db", timeout="10", term="bad")
    rc = cli.cmd_schedule(args)

    err = capsys.readouterr().err
    assert rc == 2
    assert "bad term" in err


def test_cmd_export_prints_paths(monkeypatch: pytest.MonkeyPatch, fake_conn, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "_root", lambda: Path("F:/Time-Table-Generator"))
    monkeypatch.setattr(cli.db, "connect", lambda: fake_conn)

    f1 = tmp_path / "a.xlsx"
    f2 = tmp_path / "b.xlsx"
    pdf = tmp_path / "s.pdf"
    f1.write_text("x", encoding="utf-8")
    f2.write_text("x", encoding="utf-8")
    pdf.write_text("x", encoding="utf-8")

    monkeypatch.setattr(cli, "export_excel", lambda _conn, _run_id, _out: [f1, f2])
    monkeypatch.setattr(cli, "export_pdf_summary", lambda _conn, _run_id, _out: pdf)

    rc = cli.cmd_export(Namespace(run_id="1", out="output"))

    out = capsys.readouterr().out
    assert rc == 0
    assert "Excel:" in out
    assert "PDF summary" in out


def test_cmd_serve_runs_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_run(app: str, host: str, port: int, reload: bool) -> None:
        called.update({"app": app, "host": host, "port": port, "reload": reload})

    monkeypatch.setattr(cli, "os", SimpleNamespace(environ={}, environb={}, getenv=None, setdefault=None))
    # os.environ.setdefault is used in cmd_serve; provide compatible mapping behavior.
    cli.os.environ = {}

    import sys

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=fake_run))

    rc = cli.cmd_serve(Namespace(host="127.0.0.1", port="8001", reload=False))

    assert rc == 0
    assert called["app"] == "py_timetable.web.app:app"
    assert called["port"] == 8001


def test_main_dispatches_subcommands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "cmd_init_db", lambda _a: 10)
    monkeypatch.setattr(cli, "cmd_load", lambda _a: 11)
    monkeypatch.setattr(cli, "cmd_schedule", lambda _a: 12)
    monkeypatch.setattr(cli, "cmd_export", lambda _a: 13)
    monkeypatch.setattr(cli, "cmd_serve", lambda _a: 14)

    assert cli.main(["init-db"]) == 10
    assert cli.main(["load", "--csv", "autumn.csv"]) == 11
    assert cli.main(["schedule"]) == 12
    assert cli.main(["export", "--run-id", "1"]) == 13
    assert cli.main(["serve"]) == 14
