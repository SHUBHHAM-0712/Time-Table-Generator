from __future__ import annotations

import random
from dataclasses import dataclass

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_values

from .ingest import load_assignment_map
from .db import fetch_all


@dataclass
class SlotInfo:
    slot_id: int
    day: str
    order_index: int


@dataclass
class LectureVar:
    var_index: int
    assignment_id: int
    faculty_id: int
    batch_id: int
    course_id: int
    lecture_index: int
    batch_size: int


# ---------------- LOAD DATA ---------------- #

def load_slots(conn):
    rows = fetch_all(
        conn,
        """
        SELECT
            slot_id,
            day_of_week,
            ROW_NUMBER() OVER (PARTITION BY day_of_week ORDER BY start_time) AS order_index
        FROM time_matrix
        WHERE NOT is_blackout
        """,
    )
    return [SlotInfo(int(r["slot_id"]), str(r["day_of_week"]), int(r["order_index"])) for r in rows]


def load_rooms(conn):
    return fetch_all(conn, "SELECT room_id, capacity FROM room ORDER BY capacity ASC")


def build_vars(rows):
    vars_ = []
    idx = 0
    for r in rows:
        lh = int(r["lecture_hours"])
        for k in range(lh):
            vars_.append(
                LectureVar(
                    idx,
                    r["assignment_id"],
                    r["faculty_id"],
                    r["batch_id"],
                    r["course_id"],
                    k + 1,
                    r["batch_size"],
                )
            )
            idx += 1
    return vars_


def _load_teaching_time_ranges(conn: PgConnection) -> list[tuple[str, str]]:
    rows = fetch_all(
        conn,
        """
        SELECT DISTINCT start_time::text AS st, end_time::text AS et
        FROM time_matrix
        WHERE NOT is_blackout
        ORDER BY st, et
        """,
    )
    return [(str(r["st"]), str(r["et"])) for r in rows]


def _provision_overflow_slots(conn: PgConnection, extra_needed: int) -> int:
    if extra_needed <= 0:
        return 0

    time_ranges = _load_teaching_time_ranges(conn)
    if not time_ranges:
        raise RuntimeError("No teaching slots found in time_matrix")

    overflow_days = ["Sat", "Sun", "Mon2", "Tue2", "Wed2", "Thur2", "Fri2", "Sat2", "Sun2"]
    rows_to_insert: list[tuple[str, str, str]] = []

    day_idx = 0
    slot_idx = 0
    while len(rows_to_insert) < extra_needed:
        if day_idx >= len(overflow_days):
            raise RuntimeError(
                f"Need {extra_needed} extra slots but overflow day budget is exhausted"
            )
        day = overflow_days[day_idx]
        st, et = time_ranges[slot_idx]
        rows_to_insert.append((day, st, et))
        slot_idx += 1
        if slot_idx >= len(time_ranges):
            slot_idx = 0
            day_idx += 1

    with conn.cursor() as cur:
        for day, st, et in rows_to_insert:
            cur.execute(
                """
                INSERT INTO time_matrix (day_of_week, start_time, end_time, slot_group, is_blackout)
                VALUES (%s, %s::time, %s::time, 'TEACHING', FALSE)
                ON CONFLICT (day_of_week, start_time) DO NOTHING
                """,
                (day, st, et),
            )
    return len(rows_to_insert)


# ---------------- GREEDY SCHEDULER ---------------- #

def greedy_assign(vars_, slots, rooms):
    assignment = {}

    faculty_busy = set()
    batch_busy = set()
    room_busy = set()
    batch_course_day_busy = set()
    faculty_day_slots: dict[tuple[int, str], set[int]] = {}

    for v in vars_:
        candidates = []
        for s in slots:
            # Hard constraint: one lecture of same course per batch per day.
            if (v.batch_id, v.course_id, s.day) in batch_course_day_busy:
                continue

            fac_key = (v.faculty_id, s.day)
            fac_day = faculty_day_slots.get(fac_key, set())
            # Soft penalty: prefer non-adjacent periods for faculty on same day.
            soft_penalty = 0
            if (s.order_index - 1) in fac_day:
                soft_penalty += 1
            if (s.order_index + 1) in fac_day:
                soft_penalty += 1

            for r in rooms:
                if r["capacity"] < v.batch_size:
                    continue

                if (v.faculty_id, s.slot_id) in faculty_busy:
                    continue
                if (v.batch_id, s.slot_id) in batch_busy:
                    continue
                if (r["room_id"], s.slot_id) in room_busy:
                    continue

                # Small random tie-break keeps runs from getting stuck in identical patterns.
                candidates.append((soft_penalty, random.random(), s, r))

        if not candidates:
            return None  # fail fast

        _, _, best_s, best_r = min(candidates, key=lambda x: (x[0], x[1]))

        assignment[v.var_index] = (best_s.slot_id, best_r["room_id"])
        faculty_busy.add((v.faculty_id, best_s.slot_id))
        batch_busy.add((v.batch_id, best_s.slot_id))
        room_busy.add((best_r["room_id"], best_s.slot_id))
        batch_course_day_busy.add((v.batch_id, v.course_id, best_s.day))
        faculty_day_slots.setdefault((v.faculty_id, best_s.day), set()).add(best_s.order_index)

    return assignment


# ---------------- MAIN ---------------- #

def run_scheduler(conn: PgConnection, label: str, source_csv: str, timeout_seconds=120, term=None):
    rows = load_assignment_map(conn, term=term)

    if not rows:
        raise RuntimeError("No data found")

    slots = load_slots(conn)
    rooms = load_rooms(conn)
    slot_capacity = len(slots)

    # Quick feasibility checks to avoid opaque failures later.
    batch_load: dict[int, tuple[str, int]] = {}
    faculty_load: dict[int, tuple[str, int]] = {}
    for r in rows:
        bid = int(r["batch_id"])
        bcode = str(r["batch_code"])
        fid = int(r["faculty_id"])
        fshort = str(r["faculty_short"])
        lh = int(r["lecture_hours"])

        prev_b = batch_load.get(bid, (bcode, 0))
        batch_load[bid] = (prev_b[0], prev_b[1] + lh)

        prev_f = faculty_load.get(fid, (fshort, 0))
        faculty_load[fid] = (prev_f[0], prev_f[1] + lh)

    max_batch_load = max((load for _, load in batch_load.values()), default=0)
    max_faculty_load = max((load for _, load in faculty_load.values()), default=0)
    max_required = max(max_batch_load, max_faculty_load)

    overflow_added = 0
    if max_required > slot_capacity:
        overflow_added = _provision_overflow_slots(conn, max_required - slot_capacity)
        slots = load_slots(conn)
        slot_capacity = len(slots)

    max_room_capacity = max((int(r["capacity"]) for r in rooms), default=0)
    oversized_batches = [(str(r["batch_code"]), int(r["batch_size"])) for r in rows if int(r["batch_size"]) > max_room_capacity]
    if oversized_batches:
        top = ", ".join(f"{code}:{size}>{max_room_capacity}" for code, size in oversized_batches[:5])
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule_run (label, source_csv, status, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING run_id
                """,
                (label, source_csv, "failed", f"Batch too large for any room: {top}"),
            )
            run_id = cur.fetchone()[0]
        return run_id, False, f"Infeasible: some batch sizes exceed max room capacity ({top})"

    overloaded_faculty = [(name, load) for name, load in faculty_load.values() if load > slot_capacity]
    if overloaded_faculty:
        overloaded_faculty.sort(key=lambda x: x[1], reverse=True)
        top = ", ".join(f"{name}:{load}>{slot_capacity}" for name, load in overloaded_faculty[:5])
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule_run (label, source_csv, status, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING run_id
                """,
                (label, source_csv, "failed", f"Faculty overload: {top}"),
            )
            run_id = cur.fetchone()[0]
        return run_id, False, f"Infeasible: faculty weekly load exceeds available slots ({top})"

    overloaded_batches = [(code, load) for code, load in batch_load.values() if load > slot_capacity]
    if overloaded_batches:
        overloaded_batches.sort(key=lambda x: x[1], reverse=True)
        top = ", ".join(f"{code}:{load}>{slot_capacity}" for code, load in overloaded_batches[:5])
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule_run (label, source_csv, status, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING run_id
                """,
                (label, source_csv, "failed", f"Batch overload even after overflow slots: {top}"),
            )
            run_id = cur.fetchone()[0]
        return run_id, False, f"Infeasible: batch weekly load exceeds available slots ({top})"

    vars_ = build_vars(rows)

    # SORT: big batches first
    vars_.sort(key=lambda x: -x.batch_size)

    # Try multiple attempts; longer timeout allows more random restarts.
    attempts = max(10, min(100, int(float(timeout_seconds) // 5)))
    solution = None
    for _ in range(attempts):
        solution = greedy_assign(vars_, slots.copy(), rooms)
        if solution:
            break

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO schedule_run (label, source_csv, status)
            VALUES (%s, %s, %s)
            RETURNING run_id
            """,
            (label, source_csv, "draft"),
        )
        run_id = cur.fetchone()[0]

    if not solution:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE schedule_run SET status='failed', notes=%s WHERE run_id=%s",
                (
                    "Solver could not place all lectures with current constraints",
                    run_id,
                ),
            )
        return run_id, False, "Failed: Not enough slots/rooms"

    # insert results
    rows_to_insert = []
    for v in vars_:
        slot_id, room_id = solution[v.var_index]
        rows_to_insert.append(
            (run_id, v.assignment_id, v.batch_id, room_id, slot_id, v.lecture_index)
        )

    execute_values(
        conn.cursor(),
        """
        INSERT INTO master_timetable
        (run_id, assignment_id, batch_id, room_id, slot_id, lecture_index)
        VALUES %s
        """,
        rows_to_insert,
    )

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE schedule_run SET status='completed', notes=%s WHERE run_id=%s",
            (
                f"Scheduled {len(vars_)} lectures successfully"
                + (f"; auto-added {overflow_added} overflow slots" if overflow_added else ""),
                run_id,
            ),
        )

    msg = f"Scheduled {len(vars_)} lectures successfully"
    if overflow_added:
        msg += f" (auto-added {overflow_added} overflow slots)"
    return run_id, True, msg
