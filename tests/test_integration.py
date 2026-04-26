from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from py_timetable import csp_schedule, export_views, ingest
from py_timetable.web.app import app


def test_csv_to_ingest_to_schedule_to_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_conn
) -> None:
    csv_path = tmp_path / "academic.csv"
    csv_path.write_text(
        "code,name,L-T-P-C,type,faculty,program,semester\n"
        "CS101,Intro CS,1-0-0-1,Core,Dr A,ICT,3\n",
        encoding="utf-8",
    )

    stats = ingest.ingest_academic_csv(fake_conn, csv_path, default_batch_size=60)
    assert stats["rows"] == 1

    assignment_rows = [
        {
            "assignment_id": 11,
            "faculty_id": 1,
            "faculty_short": "DRA",
            "batch_id": 21,
            "batch_code": "ICT-S3",
            "batch_size": 60,
            "course_id": 31,
            "course_code": "CS101",
            "lecture_hours": 1,
        }
    ]

    monkeypatch.setattr(csp_schedule, "load_assignment_map", lambda *_a, **_k: assignment_rows)
    monkeypatch.setattr(csp_schedule, "load_slots", lambda *_a, **_k: [csp_schedule.SlotInfo(1, "Mon", 1)])
    monkeypatch.setattr(csp_schedule, "load_rooms", lambda *_a, **_k: [{"room_id": 101, "capacity": 120}])
    monkeypatch.setattr(csp_schedule, "_mirror_run_to_legacy_tables", lambda *_a, **_k: None)

    inserted = {"rows": []}

    def fake_execute_values(_cursor, _sql, values, **_kwargs):
        inserted["rows"] = values

    monkeypatch.setattr(csp_schedule, "execute_values", fake_execute_values)

    run_id, ok, _ = csp_schedule.run_scheduler(fake_conn, label="itest", source_csv="academic.csv")

    assert ok is True
    assert run_id > 0
    assert inserted["rows"]

    events = [
        {
            "timetable_id": 1,
            "day_of_week": "Mon",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "course_code": "CS101",
            "course_title": "Intro CS",
            "faculty": "DRA",
            "batch_code": "ICT-S3",
            "program": "ICT",
            "semester": 3,
            "room_code": "R-101",
            "capacity": 120,
        }
    ]
    monkeypatch.setattr(export_views, "fetch_timetable_events", lambda *_a, **_k: events)

    files = export_views.export_excel(conn=None, run_id=run_id, out_dir=tmp_path)

    assert files
    assert all(path.exists() for path in files)


def test_root_route_returns_200() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200


def test_edge_empty_input() -> None:
    assert csp_schedule.build_vars([]) == []


def test_edge_no_available_rooms() -> None:
    vars_ = csp_schedule.build_vars(
        [
            {
                "assignment_id": 1,
                "faculty_id": 1,
                "batch_id": 1,
                "course_id": 1,
                "lecture_hours": 1,
                "batch_size": 60,
            }
        ]
    )
    slots = [csp_schedule.SlotInfo(1, "Mon", 1)]

    solution = csp_schedule.greedy_assign(vars_, slots, rooms=[])

    assert solution is None
