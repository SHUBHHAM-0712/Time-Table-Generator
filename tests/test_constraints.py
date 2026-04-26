from __future__ import annotations

from collections import defaultdict


def _no_faculty_conflict(timetable: list[dict[str, str | int]]) -> bool:
    seen: set[tuple[str, int]] = set()
    for item in timetable:
        key = (str(item["faculty"]), int(item["slot_id"]))
        if key in seen:
            return False
        seen.add(key)
    return True


def _no_room_conflict(timetable: list[dict[str, str | int]]) -> bool:
    seen: set[tuple[str, int]] = set()
    for item in timetable:
        key = (str(item["room"]), int(item["slot_id"]))
        if key in seen:
            return False
        seen.add(key)
    return True


def _no_batch_conflict(timetable: list[dict[str, str | int]]) -> bool:
    seen: set[tuple[str, int]] = set()
    for item in timetable:
        key = (str(item["batch"]), int(item["slot_id"]))
        if key in seen:
            return False
        seen.add(key)
    return True


def _same_course_same_slot(timetable: list[dict[str, str | int]]) -> bool:
    by_course: dict[tuple[str, str], set[int]] = defaultdict(set)
    for item in timetable:
        by_course[(str(item["course_code"]), str(item["course_title"]))].add(int(item["slot_id"]))

    for slot_ids in by_course.values():
        if len(slot_ids) > 1:
            return False
    return True


def test_no_faculty_room_batch_conflicts(sample_timetable) -> None:
    assert _no_faculty_conflict(sample_timetable)
    assert _no_room_conflict(sample_timetable)
    assert _no_batch_conflict(sample_timetable)


def test_same_course_across_batches_is_same_slot(sample_timetable) -> None:
    assert _same_course_same_slot(sample_timetable)


def test_detects_same_course_cross_batch_slot_violation(sample_timetable) -> None:
    violating = [dict(x) for x in sample_timetable]
    violating[1]["slot_id"] = 3

    assert _same_course_same_slot(violating) is False
