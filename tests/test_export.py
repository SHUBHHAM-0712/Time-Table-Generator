from __future__ import annotations

from pathlib import Path

import pytest

from py_timetable import export_views


def _events() -> list[dict[str, object]]:
    return [
        {
            "timetable_id": 1,
            "day_of_week": "Mon",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "course_code": "CS201",
            "course_title": "Data Structures",
            "faculty": "FAC-A",
            "batch_code": "ICT-S3-A",
            "program": "ICT",
            "semester": 3,
            "room_code": "R-101",
            "capacity": 60,
        },
        {
            "timetable_id": 2,
            "day_of_week": "Mon",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "course_code": "CS202",
            "course_title": "DBMS",
            "faculty": "FAC-B",
            "batch_code": "ICT-S3-B",
            "program": "ICT",
            "semester": 3,
            "room_code": "R-102",
            "capacity": 60,
        },
    ]


def test_export_excel_creates_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_views, "fetch_timetable_events", lambda *_args, **_kwargs: _events())

    paths = export_views.export_excel(conn=None, run_id=1, out_dir=tmp_path)

    assert paths
    assert all(path.exists() for path in paths)


def test_export_excel_raises_when_no_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_views, "fetch_timetable_events", lambda *_args, **_kwargs: [])

    with pytest.raises(RuntimeError, match="No timetable rows"):
        export_views.export_excel(conn=None, run_id=1, out_dir=tmp_path)


def test_export_pdf_summary_creates_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(export_views, "fetch_timetable_events", lambda *_args, **_kwargs: _events())

    path = export_views.export_pdf_summary(conn=None, run_id=1, out_dir=tmp_path)

    assert path.exists()
    assert path.suffix == ".pdf"
