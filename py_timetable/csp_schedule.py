from __future__ import annotations

import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from psycopg2.extensions import connection as PgConnection

from .ingest import load_assignment_map
from .db import fetch_all


@dataclass(frozen=True)
class SlotInfo:
    slot_id: int
    day_of_week: str
    start_order: int


@dataclass
class LectureVar:
    var_index: int
    assignment_id: int
    faculty_id: int
    batch_id: int
    course_id: int
    lecture_index: int
    batch_size: int
    course_code: str
    is_core: bool


def _is_core_type(course_type: str) -> bool:
    return "core" in course_type.lower() and "elective" not in course_type.lower()


def _load_teaching_slots(conn: PgConnection) -> list[SlotInfo]:
    rows = fetch_all(
        conn,
        """
        SELECT slot_id, day_of_week, start_time
        FROM time_matrix
        WHERE NOT is_blackout
        """,
    )
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_day[str(r["day_of_week"])].append(r)
    day_seq = ["Mon", "Tue", "Wed", "Thur", "Fri"]
    slots: list[SlotInfo] = []
    for day in day_seq:
        lst = sorted(by_day.get(day, []), key=lambda x: str(x["start_time"]))
        for i, r in enumerate(lst):
            slots.append(SlotInfo(int(r["slot_id"]), day, i))
    return slots


def _load_rooms(conn: PgConnection) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        "SELECT room_id, room_code, capacity FROM room ORDER BY capacity ASC",
    )


def _build_variables(rows: list[dict[str, Any]]) -> list[LectureVar]:
    vars_: list[LectureVar] = []
    idx = 0
    for r in rows:
        lh = int(r["lecture_hours"])
        if lh <= 0:
            continue
        for k in range(1, lh + 1):
            vars_.append(
                LectureVar(
                    var_index=idx,
                    assignment_id=int(r["assignment_id"]),
                    faculty_id=int(r["faculty_id"]),
                    batch_id=int(r["batch_id"]),
                    course_id=int(r["course_id"]),
                    lecture_index=k,
                    batch_size=int(r["batch_size"]),
                    course_code=str(r["course_code"]),
                    is_core=_is_core_type(str(r["course_type"])),
                )
            )
            idx += 1
    return vars_


def _faculty_course_counts(rows: list[dict[str, Any]]) -> dict[int, set[int]]:
    m: dict[int, set[int]] = {}
    for r in rows:
        m.setdefault(int(r["faculty_id"]), set()).add(int(r["course_id"]))
    return m


def _order_variables(vars_: list[LectureVar]) -> list[LectureVar]:
    fac_count: dict[int, int] = {}
    for v in vars_:
        fac_count[v.faculty_id] = fac_count.get(v.faculty_id, 0) + 1

    def sort_key(v: LectureVar) -> tuple[int, int, int, str]:
        core_rank = 0 if v.is_core else 1
        fan = -fac_count.get(v.faculty_id, 0)
        return (core_rank, fan, v.batch_id, v.course_code)

    return sorted(vars_, key=sort_key)


def _is_consecutive(si: SlotInfo, sj: SlotInfo) -> bool:
    if si.day_of_week != sj.day_of_week:
        return False
    return abs(si.start_order - sj.start_order) == 1


def _try_assign(
    ordered: list[LectureVar],
    slots: list[SlotInfo],
    rooms: list[dict[str, Any]],
    slot_by_id: dict[int, SlotInfo],
    timeout_at: float | None,
) -> dict[int, tuple[int, int]] | None:
    n = len(ordered)
    assignment: dict[int, tuple[int, int]] = {}

    batch_slot: dict[tuple[int, int], bool] = {}
    faculty_slot: dict[tuple[int, int], bool] = {}
    room_slot: dict[tuple[int, int], bool] = {}
    course_day_batch: dict[tuple[int, int, str], bool] = {}

    def can_place(v: LectureVar, slot_id: int, room_id: int) -> bool:
        if (v.batch_id, slot_id) in batch_slot:
            return False
        if (v.faculty_id, slot_id) in faculty_slot:
            return False
        if (room_id, slot_id) in room_slot:
            return False
        day = slot_by_id[slot_id].day_of_week
        if (v.batch_id, v.course_id, day) in course_day_batch:
            return False
        return True

    def register(v: LectureVar, slot_id: int, room_id: int) -> None:
        assignment[v.var_index] = (slot_id, room_id)
        batch_slot[(v.batch_id, slot_id)] = True
        faculty_slot[(v.faculty_id, slot_id)] = True
        room_slot[(room_id, slot_id)] = True
        day = slot_by_id[slot_id].day_of_week
        course_day_batch[(v.batch_id, v.course_id, day)] = True

    def unregister(v: LectureVar, slot_id: int, room_id: int) -> None:
        del assignment[v.var_index]
        del batch_slot[(v.batch_id, slot_id)]
        del faculty_slot[(v.faculty_id, slot_id)]
        del room_slot[(room_id, slot_id)]
        day = slot_by_id[slot_id].day_of_week
        del course_day_batch[(v.batch_id, v.course_id, day)]

    def backtrack(i: int) -> bool:
        if timeout_at is not None and time.monotonic() > timeout_at:
            return False
        if i == n:
            return True
        v = ordered[i]
        eligible_rooms = [rm for rm in rooms if int(rm["capacity"]) >= v.batch_size]
        if not eligible_rooms:
            return False

        slot_order = list(slots)
        random.shuffle(slot_order)

        for s in slot_order:
            slot_id = s.slot_id
            for rm in eligible_rooms:
                room_id = int(rm["room_id"])
                if not can_place(v, slot_id, room_id):
                    continue
                register(v, slot_id, room_id)
                if backtrack(i + 1):
                    return True
                unregister(v, slot_id, room_id)
        return False

    if backtrack(0):
        return assignment
    return None


def _soft_improve_clean(
    assignment: dict[int, tuple[int, int]],
    ordered: list[LectureVar],
    slot_by_id: dict[int, SlotInfo],
    iterations: int = 350,
) -> dict[int, tuple[int, int]]:
    def penalty(a: dict[int, tuple[int, int]]) -> int:
        by_fac: dict[int, list[SlotInfo]] = {}
        for v in ordered:
            sid, _ = a[v.var_index]
            by_fac.setdefault(v.faculty_id, []).append(slot_by_id[sid])
        pen = 0
        for lst in by_fac.values():
            lst.sort(key=lambda s: (s.day_of_week, s.start_order))
            for x, y in zip(lst, lst[1:]):
                if _is_consecutive(x, y):
                    pen += 1
        return pen

    def is_valid(a: dict[int, tuple[int, int]]) -> bool:
        bs: set[tuple[int, int]] = set()
        fs: set[tuple[int, int]] = set()
        rs: set[tuple[int, int]] = set()
        cd: set[tuple[int, int, str]] = set()
        for v in ordered:
            sid, rid = a[v.var_index]
            if (v.batch_id, sid) in bs:
                return False
            bs.add((v.batch_id, sid))
            if (v.faculty_id, sid) in fs:
                return False
            fs.add((v.faculty_id, sid))
            if (rid, sid) in rs:
                return False
            rs.add((rid, sid))
            day = slot_by_id[sid].day_of_week
            key = (v.batch_id, v.course_id, day)
            if key in cd:
                return False
            cd.add(key)
        return True

    best = dict(assignment)
    best_pen = penalty(best)
    cur = dict(assignment)
    for _ in range(iterations):
        if len(ordered) < 2:
            break
        i, j = random.sample(range(len(ordered)), 2)
        vi, vj = ordered[i], ordered[j]
        si, ri = cur[vi.var_index]
        sj, rj = cur[vj.var_index]
        if si == sj:
            continue
        cur[vi.var_index] = (sj, ri)
        cur[vj.var_index] = (si, rj)
        if not is_valid(cur):
            cur[vi.var_index] = (si, ri)
            cur[vj.var_index] = (sj, rj)
            continue
        pen = penalty(cur)
        if pen <= best_pen:
            best_pen = pen
            best = dict(cur)
        else:
            cur[vi.var_index] = (si, ri)
            cur[vj.var_index] = (sj, rj)
    return best


def run_scheduler(
    conn: PgConnection,
    label: str,
    source_csv: str,
    timeout_seconds: float = 120.0,
    term: str | None = None,
) -> tuple[int, bool, str]:
    rows = load_assignment_map(conn, term=term)
    if not rows:
        raise RuntimeError(
            "No offerings for this term in the database — run SQL seeds or pick another term."
        )

    fac_counts = _faculty_course_counts(rows)
    overload = [fid for fid, cs in fac_counts.items() if len(cs) > 3]
    warn = ""
    if overload:
        warn = (
            f"Note: {len(overload)} faculty teach more than 3 distinct courses in this run "
            "(soft guideline FR3.3.3).\n"
        )

    slots = _load_teaching_slots(conn)
    if not slots:
        raise RuntimeError("No teaching slots — load time_matrix from timeslots.csv.")

    rooms = _load_rooms(conn)
    if not rooms:
        raise RuntimeError("No rooms — run seed SQL.")

    slot_by_id = {s.slot_id: s for s in slots}

    raw_vars = _build_variables(rows)
    ordered = _order_variables(raw_vars)

    timeout_at = time.monotonic() + timeout_seconds
    sol = _try_assign(ordered, slots, rooms, slot_by_id, timeout_at)

    tnorm = (term or "all").strip().lower() or "all"
    if tnorm == "":
        tnorm = "all"
    run_notes = f"term={tnorm}"

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO schedule_run (label, source_csv, status, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING run_id
            """,
            (label, source_csv, "draft", run_notes),
        )
        run_id = int(cur.fetchone()[0])

    if sol is None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conflict_report (run_id, severity, category, detail)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    run_id,
                    "high",
                    "CSP",
                    "No conflict-free assignment found within time limit. "
                    "Add rooms, reduce offerings per run, or split by semester.",
                ),
            )
            cur.execute(
                "UPDATE schedule_run SET status = %s, notes = %s WHERE run_id = %s",
                ("failed", f"{run_notes}; CSP unsatisfiable", run_id),
            )
        return run_id, False, warn + "Scheduling failed — see conflict_report."

    sol = _soft_improve_clean(sol, ordered, slot_by_id)

    insert_sql = """
        INSERT INTO master_timetable (run_id, assignment_id, batch_id, room_id, slot_id, lecture_index)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        for v in ordered:
            slot_id, room_id = sol[v.var_index]
            cur.execute(
                insert_sql,
                (run_id, v.assignment_id, v.batch_id, room_id, slot_id, v.lecture_index),
            )
        cur.execute(
            "UPDATE schedule_run SET status = %s WHERE run_id = %s",
            ("completed", run_id),
        )

    return run_id, True, warn + f"Scheduled run_id={run_id} ({run_notes}) with {len(ordered)} lecture events."
