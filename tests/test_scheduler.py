from __future__ import annotations

import time

import pytest
import psycopg2

from py_timetable import csp_schedule


def test_build_vars_expands_by_lecture_hours() -> None:
    rows = [
        {
            "assignment_id": 11,
            "faculty_id": 1,
            "batch_id": 21,
            "course_id": 31,
            "lecture_hours": 3,
            "batch_size": 50,
        }
    ]

    vars_ = csp_schedule.build_vars(rows)

    assert len(vars_) == 3
    assert [v.lecture_index for v in vars_] == [1, 2, 3]


def test_greedy_assign_generates_schedule() -> None:
    rows = [
        {
            "assignment_id": 11,
            "faculty_id": 1,
            "batch_id": 21,
            "course_id": 31,
            "lecture_hours": 1,
            "batch_size": 40,
        },
        {
            "assignment_id": 12,
            "faculty_id": 2,
            "batch_id": 22,
            "course_id": 32,
            "lecture_hours": 1,
            "batch_size": 40,
        },
    ]
    vars_ = csp_schedule.build_vars(rows)
    slots = [
        csp_schedule.SlotInfo(1, "Mon", 1),
        csp_schedule.SlotInfo(2, "Mon", 2),
    ]
    rooms = [{"room_id": 101, "capacity": 60}]

    solution = csp_schedule.greedy_assign(vars_, slots, rooms)

    assert solution is not None
    assert len(solution) == len(vars_)


def test_run_scheduler_empty_input_raises(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    monkeypatch.setattr(csp_schedule, "load_assignment_map", lambda *_args, **_kwargs: [])

    with pytest.raises(RuntimeError, match="No data found"):
        csp_schedule.run_scheduler(fake_conn, label="t1", source_csv="db")


def test_conflicting_data_same_faculty_everywhere_returns_none() -> None:
    rows = [
        {
            "assignment_id": 11,
            "faculty_id": 1,
            "batch_id": 21,
            "course_id": 31,
            "lecture_hours": 1,
            "batch_size": 40,
        },
        {
            "assignment_id": 12,
            "faculty_id": 1,
            "batch_id": 22,
            "course_id": 32,
            "lecture_hours": 1,
            "batch_size": 40,
        },
    ]
    vars_ = csp_schedule.build_vars(rows)
    slots = [csp_schedule.SlotInfo(1, "Mon", 1)]
    rooms = [{"room_id": 101, "capacity": 60}]

    solution = csp_schedule.greedy_assign(vars_, slots, rooms)

    assert solution is None


def test_run_scheduler_no_available_rooms(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    rows = [
        {
            "assignment_id": 11,
            "faculty_id": 1,
            "faculty_short": "F1",
            "batch_id": 21,
            "batch_code": "B1",
            "batch_size": 55,
            "course_id": 31,
            "course_code": "CS101",
            "lecture_hours": 1,
        }
    ]

    monkeypatch.setattr(csp_schedule, "load_assignment_map", lambda *_args, **_kwargs: rows)
    monkeypatch.setattr(csp_schedule, "load_slots", lambda *_args, **_kwargs: [csp_schedule.SlotInfo(1, "Mon", 1)])
    monkeypatch.setattr(csp_schedule, "load_rooms", lambda *_args, **_kwargs: [])

    run_id, ok, msg = csp_schedule.run_scheduler(fake_conn, label="t2", source_csv="db")

    assert run_id > 0
    assert ok is False
    assert "Infeasible" in msg


def test_load_slots_and_rooms(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    slot_rows = [{"slot_id": 1, "day_of_week": "Mon", "order_index": 1}]
    room_rows = [{"room_id": 9, "capacity": 80}]

    def fake_fetch_all(_conn, query, *_args, **_kwargs):
        if "FROM time_matrix" in query:
            return slot_rows
        return room_rows

    monkeypatch.setattr(csp_schedule, "fetch_all", fake_fetch_all)

    slots = csp_schedule.load_slots(fake_conn)
    rooms = csp_schedule.load_rooms(fake_conn)

    assert slots[0].slot_id == 1
    assert rooms[0]["room_id"] == 9


def test_load_teaching_time_ranges(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    monkeypatch.setattr(
        csp_schedule,
        "fetch_all",
        lambda *_a, **_k: [{"st": "09:00:00", "et": "10:00:00"}],
    )

    ranges = csp_schedule._load_teaching_time_ranges(fake_conn)

    assert ranges == [("09:00:00", "10:00:00")]


def test_provision_overflow_slots_noop(fake_conn) -> None:
    assert csp_schedule._provision_overflow_slots(fake_conn, 0) == 0


def test_provision_overflow_slots_raises_without_ranges(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    monkeypatch.setattr(csp_schedule, "_load_teaching_time_ranges", lambda _conn: [])

    with pytest.raises(RuntimeError, match="No teaching slots"):
        csp_schedule._provision_overflow_slots(fake_conn, 2)


def test_provision_overflow_slots_inserts_rows(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    monkeypatch.setattr(csp_schedule, "_load_teaching_time_ranges", lambda _conn: [("09:00:00", "10:00:00")])

    count = csp_schedule._provision_overflow_slots(fake_conn, 2)

    assert count == 2
    executed_sql = "\n".join(q for q, _ in fake_conn.executed)
    assert "INSERT INTO time_matrix" in executed_sql


def test_run_scheduler_overloaded_faculty_branch(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    rows = [
        {
            "assignment_id": 1,
            "faculty_id": 10,
            "faculty_short": "FAC",
            "batch_id": 21,
            "batch_code": "B1",
            "batch_size": 30,
            "course_id": 31,
            "course_code": "CS1",
            "lecture_hours": 2,
        }
    ]
    monkeypatch.setattr(csp_schedule, "load_assignment_map", lambda *_a, **_k: rows)
    monkeypatch.setattr(csp_schedule, "load_slots", lambda *_a, **_k: [csp_schedule.SlotInfo(1, "Mon", 1)])
    monkeypatch.setattr(csp_schedule, "load_rooms", lambda *_a, **_k: [{"room_id": 1, "capacity": 100}])
    monkeypatch.setattr(csp_schedule, "_provision_overflow_slots", lambda *_a, **_k: 0)

    run_id, ok, msg = csp_schedule.run_scheduler(fake_conn, label="over-fac", source_csv="db")

    assert run_id > 0
    assert ok is False
    assert "faculty weekly load exceeds available slots" in msg.lower()


def test_run_scheduler_solver_failure_updates_run(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    rows = [
        {
            "assignment_id": 1,
            "faculty_id": 2,
            "faculty_short": "FAC2",
            "batch_id": 3,
            "batch_code": "B3",
            "batch_size": 40,
            "course_id": 4,
            "course_code": "CS4",
            "lecture_hours": 1,
        }
    ]
    monkeypatch.setattr(csp_schedule, "load_assignment_map", lambda *_a, **_k: rows)
    monkeypatch.setattr(csp_schedule, "load_slots", lambda *_a, **_k: [csp_schedule.SlotInfo(1, "Mon", 1)])
    monkeypatch.setattr(csp_schedule, "load_rooms", lambda *_a, **_k: [{"room_id": 1, "capacity": 100}])
    monkeypatch.setattr(csp_schedule, "greedy_assign", lambda *_a, **_k: None)

    run_id, ok, msg = csp_schedule.run_scheduler(fake_conn, label="solver-fail", source_csv="db")

    assert run_id > 0
    assert ok is False
    assert "Failed: Not enough slots/rooms" == msg
    all_sql = "\n".join(q for q, _ in fake_conn.executed)
    assert "UPDATE schedule_run SET status='failed'" in all_sql


def test_run_scheduler_success_path(monkeypatch: pytest.MonkeyPatch, fake_conn) -> None:
    rows = [
        {
            "assignment_id": 7,
            "faculty_id": 8,
            "faculty_short": "F8",
            "batch_id": 9,
            "batch_code": "B9",
            "batch_size": 40,
            "course_id": 10,
            "course_code": "CS10",
            "lecture_hours": 1,
        }
    ]
    monkeypatch.setattr(csp_schedule, "load_assignment_map", lambda *_a, **_k: rows)
    monkeypatch.setattr(csp_schedule, "load_slots", lambda *_a, **_k: [csp_schedule.SlotInfo(1, "Mon", 1)])
    monkeypatch.setattr(csp_schedule, "load_rooms", lambda *_a, **_k: [{"room_id": 101, "capacity": 80}])
    monkeypatch.setattr(csp_schedule, "_mirror_run_to_legacy_tables", lambda *_a, **_k: None)

    captured = {"rows": []}

    def fake_execute_values(_cur, _sql, rows_to_insert):
        captured["rows"] = rows_to_insert

    monkeypatch.setattr(csp_schedule, "execute_values", fake_execute_values)

    run_id, ok, msg = csp_schedule.run_scheduler(fake_conn, label="ok", source_csv="db")

    assert run_id > 0
    assert ok is True
    assert "Scheduled" in msg
    assert len(captured["rows"]) == 1


def test_mirror_legacy_rolls_back_on_db_error() -> None:
    class FailingCursor:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            self.calls.append((query, params))
            if "INSERT INTO timetable_session (" in query:
                raise psycopg2.Error("boom")

    class FailingConn:
        def __init__(self):
            self.cur = FailingCursor()

        def cursor(self):
            return self.cur

    conn = FailingConn()

    csp_schedule._mirror_run_to_legacy_tables(conn, 1)

    sql_text = "\n".join(q for q, _ in conn.cur.calls)
    assert "ROLLBACK TO SAVEPOINT tt_legacy_mirror" in sql_text


@pytest.mark.performance
def test_performance_timetable_generation_under_10_seconds() -> None:
    rows = []
    for i in range(60):
        rows.append(
            {
                "assignment_id": 1000 + i,
                "faculty_id": 2000 + i,
                "batch_id": 3000 + i,
                "course_id": 4000 + i,
                "lecture_hours": 1,
                "batch_size": 45,
            }
        )

    vars_ = csp_schedule.build_vars(rows)
    slots = [csp_schedule.SlotInfo(i + 1, "Mon", i + 1) for i in range(60)]
    rooms = [{"room_id": 101, "capacity": 80}]

    start = time.perf_counter()
    solution = csp_schedule.greedy_assign(vars_, slots, rooms)
    elapsed = time.perf_counter() - start

    assert solution is not None
    assert elapsed < 10.0
