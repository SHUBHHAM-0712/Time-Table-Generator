from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class FakeCursor:
    conn: "FakeConnection"

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, query: str, params: Any = None) -> None:
        self.conn.executed.append((query, params))

    def executemany(self, query: str, seq: list[Any]) -> None:
        self.conn.executed.append((query, seq))

    def fetchone(self) -> Any:
        if self.conn.fetchone_queue:
            return self.conn.fetchone_queue.pop(0)
        current = self.conn.next_id
        self.conn.next_id += 1
        return (current,)

    def fetchall(self) -> list[Any]:
        return list(self.conn.fetchall_result)


class FakeConnection:
    def __init__(self, *, fetchone_queue: list[Any] | None = None, fetchall_result: list[Any] | None = None):
        self.executed: list[tuple[Any, Any]] = []
        self.fetchone_queue = list(fetchone_queue or [])
        self.fetchall_result = list(fetchall_result or [])
        self.next_id = 1
        self.autocommit = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory: Any = None) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_conn() -> FakeConnection:
    return FakeConnection()


@pytest.fixture
def sample_courses() -> list[dict[str, Any]]:
    return [
        {
            "assignment_id": 101,
            "faculty_id": 11,
            "faculty_short": "FAC-A",
            "batch_id": 201,
            "batch_code": "ICT-S3-A",
            "batch_size": 55,
            "course_id": 301,
            "course_code": "CS201",
            "course_title": "Data Structures",
            "lecture_hours": 1,
        },
        {
            "assignment_id": 102,
            "faculty_id": 12,
            "faculty_short": "FAC-B",
            "batch_id": 202,
            "batch_code": "ICT-S3-B",
            "batch_size": 58,
            "course_id": 302,
            "course_code": "CS202",
            "course_title": "DBMS",
            "lecture_hours": 1,
        },
    ]


@pytest.fixture
def sample_superblocks(sample_courses: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    blocks: dict[str, list[dict[str, Any]]] = {}
    for c in sample_courses:
        key = f"{c['course_code']}::{c['course_title']}"
        blocks.setdefault(key, []).append(c)
    return blocks


@pytest.fixture
def sample_timetable() -> list[dict[str, Any]]:
    return [
        {
            "slot_id": 1,
            "faculty": "FAC-A",
            "room": "R-101",
            "batch": "ICT-S3-A",
            "course_code": "CS301",
            "course_title": "Algorithms",
        },
        {
            "slot_id": 1,
            "faculty": "FAC-B",
            "room": "R-102",
            "batch": "ICT-S3-B",
            "course_code": "CS301",
            "course_title": "Algorithms",
        },
        {
            "slot_id": 2,
            "faculty": "FAC-C",
            "room": "R-201",
            "batch": "ICT-S5-A",
            "course_code": "CS401",
            "course_title": "Networks",
        },
    ]
