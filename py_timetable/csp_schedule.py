from __future__ import annotations

import random
from dataclasses import dataclass, field

import psycopg2
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
    # For merged lectures: list of (batch_id, batch_size) tuples
    merged_batches: list[tuple[int, int]] = field(default_factory=list)
    is_merged: bool = False


# Allowed batches for merging
MERGEABLE_BATCH_PROGRAMS = {"ICTB", "MNC", "EVD", "CS"}


def _extract_program_from_batch_code(batch_code: str) -> str:
    """Extract program code from batch_code (e.g., 'ICTB' from 'ICTB-S1')."""
    if isinstance(batch_code, str):
        parts = batch_code.split("-")
        return parts[0] if parts else ""
    return ""


# ---------------- LOAD DATA ---------------- #

def merge_batches_by_course_and_faculty(rows: list[dict]) -> list[dict]:
    """
    Merge rows for batches that have the same course_code and faculty,
    combining them into single offerings with merged batch information.
    
    IMPORTANT: Only batches from the allowed programs (ICTB, MNC, EVD, CS) are merged.
    Batches from other programs (e.g., ICTA) are kept separate in all cases.
    
    Returns list of merged rows, where:
    - Each row represents a unique (course_code, faculty_id, semester) combination
    - batch_id is the first batch in the group
    - All merged batch IDs and sizes are stored in merged_batch_ids and merged_batch_sizes
    - is_merged flag indicates if this row represents multiple batches
    
    Note: Merging only happens if all rows have 'course_code', 'semester', and 'batch_code' fields.
    If these fields are missing (e.g., in tests), rows are returned as-is with
    metadata initialized.
    """
    # Check if rows have necessary fields for merging
    if not rows or not all("course_code" in r and "semester" in r for r in rows):
        # No merging possible; just add metadata and return
        result = []
        for row in rows:
            r = row.copy()
            r["merged_batch_ids"] = r.get("merged_batch_ids", [int(r["batch_id"])])
            r["merged_batch_sizes"] = r.get("merged_batch_sizes", [int(r["batch_size"])])
            r["is_merged"] = r.get("is_merged", False)
            r["total_batch_size"] = r.get("total_batch_size", int(r["batch_size"]))
            result.append(r)
        return result
    
    # Group by (course_code, faculty_id, semester)
    groups = {}
    for row in rows:
        key = (
            str(row["course_code"]),
            int(row["faculty_id"]),
            int(row["semester"]),
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    
    merged_rows = []
    for group in groups.values():
        # Separate batches into mergeable and non-mergeable
        mergeable_batches = []
        non_mergeable_batches = []
        
        for row in group:
            program = _extract_program_from_batch_code(str(row.get("batch_code", "")))
            if program in MERGEABLE_BATCH_PROGRAMS:
                mergeable_batches.append(row)
            else:
                non_mergeable_batches.append(row)
        
        # Process mergeable batches
        if len(mergeable_batches) > 1:
            # Multiple mergeable batches → merge them
            merged_row = mergeable_batches[0].copy()
            merged_batch_ids = [int(r["batch_id"]) for r in mergeable_batches]
            merged_batch_sizes = [int(r["batch_size"]) for r in mergeable_batches]
            total_size = sum(merged_batch_sizes)
            
            merged_row["merged_batch_ids"] = merged_batch_ids
            merged_row["merged_batch_sizes"] = merged_batch_sizes
            merged_row["total_batch_size"] = total_size
            merged_row["is_merged"] = True
            merged_row["batch_id"] = merged_batch_ids[0]
            merged_row["batch_size"] = total_size
            
            merged_rows.append(merged_row)
        elif len(mergeable_batches) == 1:
            # Single mergeable batch → keep separate
            row = mergeable_batches[0].copy()
            row["merged_batch_ids"] = [int(row["batch_id"])]
            row["merged_batch_sizes"] = [int(row["batch_size"])]
            row["is_merged"] = False
            row["total_batch_size"] = int(row["batch_size"])
            merged_rows.append(row)
        
        # Process non-mergeable batches (each stays separate)
        for row in non_mergeable_batches:
            r = row.copy()
            r["merged_batch_ids"] = [int(r["batch_id"])]
            r["merged_batch_sizes"] = [int(r["batch_size"])]
            r["is_merged"] = False
            r["total_batch_size"] = int(r["batch_size"])
            merged_rows.append(r)
    
    return merged_rows


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
        merged_batch_ids = r.get("merged_batch_ids", [int(r["batch_id"])])
        merged_batch_sizes = r.get("merged_batch_sizes", [int(r["batch_size"])])
        is_merged = r.get("is_merged", False)
        total_size = r.get("total_batch_size", int(r["batch_size"]))
        
        for k in range(lh):
            lecture_var = LectureVar(
                idx,
                r["assignment_id"],
                r["faculty_id"],
                int(r["batch_id"]),  # Primary batch ID
                r["course_id"],
                k + 1,
                total_size,  # Use combined size for room allocation
            )
            
            # Store merged batch information
            if is_merged:
                lecture_var.is_merged = True
                lecture_var.merged_batches = list(zip(merged_batch_ids, merged_batch_sizes))
            else:
                lecture_var.is_merged = False
                lecture_var.merged_batches = [(int(r["batch_id"]), int(r["batch_size"]))]
            
            vars_.append(lecture_var)
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
            # For merged lectures, check ALL batches in the merged group
            if v.is_merged:
                # Check if any batch in the merged group is busy for this course on this day
                skip_slot = False
                for batch_id, _ in v.merged_batches:
                    if (batch_id, v.course_id, s.day) in batch_course_day_busy:
                        skip_slot = True
                        break
                if skip_slot:
                    continue
            else:
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
                
                # For merged lectures, check that NONE of the batches have a conflict
                if v.is_merged:
                    skip_room = False
                    for batch_id, _ in v.merged_batches:
                        if (batch_id, s.slot_id) in batch_busy:
                            skip_room = True
                            break
                    if skip_room:
                        continue
                else:
                    if (v.batch_id, s.slot_id) in batch_busy:
                        continue
                
                if (r["room_id"], s.slot_id) in room_busy:
                    continue

                # Small random tie-break keeps runs from getting stuck in identical patterns.
                candidates.append((soft_penalty, random.random(), s, r))

        if not candidates:
            return None  # fail fast

        _, _, best_s, best_r = min(candidates, key=lambda x: (x[1], x[1]))

        assignment[v.var_index] = (best_s.slot_id, best_r["room_id"])
        faculty_busy.add((v.faculty_id, best_s.slot_id))
        
        # Mark all merged batches as busy
        if v.is_merged:
            for batch_id, _ in v.merged_batches:
                batch_busy.add((batch_id, best_s.slot_id))
                batch_course_day_busy.add((batch_id, v.course_id, best_s.day))
        else:
            batch_busy.add((v.batch_id, best_s.slot_id))
            batch_course_day_busy.add((v.batch_id, v.course_id, best_s.day))
        
        room_busy.add((best_r["room_id"], best_s.slot_id))
        faculty_day_slots.setdefault((v.faculty_id, best_s.day), set()).add(best_s.order_index)

    return assignment


# ---------------- MAIN ---------------- #

def run_scheduler(conn: PgConnection, label: str, source_csv: str, timeout_seconds=120, term=None):
    rows = load_assignment_map(conn, term=term)

    if not rows:
        raise RuntimeError("No data found")

    # Merge batches with same course and faculty
    rows = merge_batches_by_course_and_faculty(rows)

    slots = load_slots(conn)
    rooms = load_rooms(conn)
    slot_capacity = len(slots)

    # Quick feasibility checks to avoid opaque failures later.
    batch_load: dict[int, tuple[str, int]] = {}
    faculty_load: dict[int, tuple[str, int]] = {}
    for r in rows:
        # For feasibility checks, calculate load for each individual batch
        merged_batch_ids = r.get("merged_batch_ids", [int(r["batch_id"])])
        fid = int(r["faculty_id"])
        fshort = str(r["faculty_short"])
        lh = int(r["lecture_hours"])

        # Each batch in merged group gets the full lecture hours
        # (they all attend the same merged lecture)
        for bid in merged_batch_ids:
            bcode = str(r["batch_code"])  # Will be same for all in group
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
        
        # For merged lectures, insert ONE row with all merged batch IDs tracked
        if v.is_merged:
            # Track all batch IDs in the merge as comma-separated string
            merged_batch_ids = ",".join(str(b[0]) for b in v.merged_batches)
            batch_id = v.merged_batches[0][0]  # Use first batch as representative
            rows_to_insert.append(
                (run_id, v.assignment_id, batch_id, room_id, slot_id, v.lecture_index, merged_batch_ids, True)
            )
        else:
            rows_to_insert.append(
                (run_id, v.assignment_id, v.batch_id, room_id, slot_id, v.lecture_index, None, False)
            )

    execute_values(
        conn.cursor(),
        """
        INSERT INTO master_timetable
        (run_id, assignment_id, batch_id, room_id, slot_id, lecture_index, merged_batch_ids, is_merged)
        VALUES %s
        """,
        rows_to_insert,
    )

    _mirror_run_to_legacy_tables(conn, run_id)

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


def _mirror_run_to_legacy_tables(conn: PgConnection, run_id: int) -> None:
    """Best-effort compatibility mirror for deployments that still read legacy tables."""
    with conn.cursor() as cur:
        cur.execute("SAVEPOINT tt_legacy_mirror")
        try:
            cur.execute(
                """
                INSERT INTO timetable_session (
                    run_id,
                    assignment_id,
                    room_id,
                    slot_id,
                    lecture_index,
                    course_id,
                    faculty_id,
                    course_code,
                    course_title,
                    total_students,
                    batch_count,
                    merged,
                    group_signature,
                    faculty_label
                )
                SELECT
                    mt.run_id,
                    mt.assignment_id,
                    mt.room_id,
                    mt.slot_id,
                    mt.lecture_index,
                    c.course_id,
                    f.faculty_id,
                    c.code,
                    c.title,
                    COUNT(DISTINCT mt.batch_id) * MAX(sb.batch_size) AS total_students,
                    COUNT(DISTINCT mt.batch_id) AS batch_count,
                    CASE WHEN COUNT(DISTINCT mt.batch_id) > 1 THEN TRUE ELSE FALSE END AS merged,
                    CONCAT(mt.run_id, ':', mt.assignment_id, ':', mt.slot_id, ':', mt.lecture_index),
                    f.short_name
                FROM master_timetable mt
                JOIN faculty_course_map fcm ON fcm.assignment_id = mt.assignment_id
                JOIN course c ON c.course_id = fcm.course_id
                JOIN faculty f ON f.faculty_id = fcm.faculty_id
                JOIN student_batch sb ON sb.batch_id = mt.batch_id
                WHERE mt.run_id = %s
                GROUP BY mt.run_id, mt.assignment_id, mt.room_id, mt.slot_id, mt.lecture_index, c.course_id, f.faculty_id, c.code, c.title, f.short_name
                ON CONFLICT (run_id, assignment_id, slot_id) DO NOTHING
                """,
                (run_id,),
            )

            cur.execute(
                """
                INSERT INTO timetable_session_batch (session_id, batch_id)
                SELECT ts.session_id, mt.batch_id
                FROM master_timetable mt
                JOIN timetable_session ts
                  ON ts.run_id = mt.run_id
                 AND ts.assignment_id = mt.assignment_id
                 AND ts.room_id = mt.room_id
                 AND ts.slot_id = mt.slot_id
                 AND ts.lecture_index = mt.lecture_index
                WHERE mt.run_id = %s
                ON CONFLICT (session_id, batch_id) DO NOTHING
                """,
                (run_id,),
            )
            cur.execute("RELEASE SAVEPOINT tt_legacy_mirror")
        except psycopg2.Error:
            # Optional compatibility path: preserve successful scheduling even if
            # legacy tables are absent or use a different schema.
            cur.execute("ROLLBACK TO SAVEPOINT tt_legacy_mirror")
            cur.execute("RELEASE SAVEPOINT tt_legacy_mirror")
