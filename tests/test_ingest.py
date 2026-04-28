from __future__ import annotations

from pathlib import Path

import pytest

from py_timetable import ingest


def test_parse_ltp_valid_values() -> None:
    lh, th, ph, cr = ingest._parse_ltp("3-1-2-4")
    assert (lh, th, ph, cr) == (3, 1, 2, 4.0)


def test_parse_ltp_invalid_values() -> None:
    assert ingest._parse_ltp("bad") == (0, 0, 0, 0.0)


def test_norm_faculty_key() -> None:
    assert ingest._norm_faculty_key("  A   B  ") == "A B"
    assert ingest._norm_faculty_key("   ") == "UNKNOWN"


def test_load_time_matrix_parses_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_conn) -> None:
    csv_path = tmp_path / "slots.csv"
    csv_path.write_text(
        "Day,StartTime,EndTime,IsLunch\n"
        "Mon,09:00,10:00,no\n"
        "Mon,13:00,14:00,yes\n",
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_execute_values(cur, query, rows, template=None):
        captured["rows"] = rows
        captured["template"] = template

    monkeypatch.setattr(ingest, "execute_values", fake_execute_values)

    count = ingest.load_time_matrix(fake_conn, csv_path)

    assert count == 2
    assert any("DELETE FROM timetable_session_batch" in q for q, _ in fake_conn.executed)
    assert any("DELETE FROM timetable_session" in q for q, _ in fake_conn.executed)
    assert any("DELETE FROM time_matrix" in q for q, _ in fake_conn.executed)
    rows = captured["rows"]
    assert isinstance(rows, list)
    assert rows[0][3] == "TEACHING"
    assert rows[1][3] == "BLACKOUT"


def test_get_default_batch_size(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    monkeypatch.setattr(ingest, "fetch_one", lambda *_args, **_kwargs: {"value_json": "75"})
    assert ingest.get_default_batch_size(fake_conn) == 75


def test_ingest_academic_csv_counts_rows_and_preserves_run_history(
    tmp_path: Path, fake_conn
) -> None:
    csv_path = tmp_path / "academic.csv"
    csv_path.write_text(
        "code,name,L-T-P-C,type,faculty,program,semester\n"
        "CS101,Intro CS,3-0-0-3,Core,Dr A,ICT,3\n"
        "CS102,Seminar,0-0-0-1,Core,Dr B,ICT,3\n",
        encoding="utf-8",
    )

    stats = ingest.ingest_academic_csv(fake_conn, csv_path, default_batch_size=60)

    assert stats["rows"] == 1
    assert stats["skipped_zero_lecture"] == 1
    all_queries = "\n".join(q for q, _ in fake_conn.executed)
    assert "DELETE FROM batch_course_map" in all_queries
    assert "DELETE FROM schedule_run" not in all_queries
    assert "DELETE FROM master_timetable" not in all_queries
