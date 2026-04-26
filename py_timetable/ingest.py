from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_values

from .db import fetch_all, fetch_one


def _parse_ltp(ltp: str) -> tuple[int, int, int, float]:
    parts = ltp.replace(" ", "").split("-")
    if len(parts) < 4:
        return 0, 0, 0, 0.0
    def _num(x: str) -> float:
        try:
            return float(x)
        except ValueError:
            return 0.0
    lh = int(_num(parts[0]))
    th = int(_num(parts[1]))
    ph = int(_num(parts[2]))
    cr = _num(parts[3])
    return lh, th, ph, cr


def _norm_faculty_key(name: str) -> str:
    s = name.strip()
    if not s:
        return "UNKNOWN"
    return re.sub(r"\s+", " ", s)[:128]


def _elective_slot(course_type: str, code: str) -> str | None:
    ct = course_type.lower()
    if "core" in ct and "elective" not in ct:
        return None
    if "elective" in ct or "honours" in ct:
        raw = f"{code}|{course_type}".encode()
        h = int(hashlib.md5(raw).hexdigest()[:8], 16) % 7
        return f"EL-{h}"
    return None


def load_time_matrix(conn: PgConnection, path: Path) -> int:
    """Load timeslots from CSV; lunch rows are blackouts."""
    rows: list[tuple[Any, ...]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            day = (r.get("Day") or "").strip()
            st = (r.get("StartTime") or "").strip()
            et = (r.get("EndTime") or "").strip()
            lunch = (r.get("IsLunch") or "").strip().lower()
            if not day or not st or not et:
                continue
            is_blackout = lunch in ("yes", "y", "true", "1")
            grp = "BLACKOUT" if is_blackout else "TEACHING"
            rows.append((day, st, et, grp, is_blackout))

    if not rows:
        return 0

    with conn.cursor() as cur:
        cur.execute("DELETE FROM time_matrix")
        execute_values(
            cur,
            """
            INSERT INTO time_matrix (day_of_week, start_time, end_time, slot_group, is_blackout)
            VALUES %s
            """,
            rows,
            template="(%s, %s::time, %s::time, %s, %s)",
        )
    return len(rows)


def get_default_batch_size(conn: PgConnection) -> int:
    row = fetch_one(
        conn,
        "SELECT value_json FROM constraint_config WHERE key = %s",
        ("default_batch_size",),
    )
    if not row:
        return 60
    v = row["value_json"]
    if isinstance(v, int):
        return int(v)
    if isinstance(v, str):
        return int(v.strip('"') or 60)
    return 60


def ingest_academic_csv(conn: PgConnection, path: Path, default_batch_size: int) -> dict[str, int]:
    """Load faculty, course, batch, faculty_course_map, batch_course_map from autumn/winter style CSV."""
    stats = {"rows": 0, "courses": 0, "skipped_zero_lecture": 0}

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = [str(x).strip().lower() for x in (reader.fieldnames or []) if x is not None]
        expected = {"code", "name", "l-t-p-c", "type", "faculty", "program", "semester"}

    if expected.issubset(set(fieldnames)):
        with path.open(newline="", encoding="utf-8") as f:
            academic_rows = list(csv.DictReader(f))
    else:
        # Accept legacy/headerless CSV in fixed order:
        # code,name,L-T-P-C,type,faculty,program,semester
        academic_rows = []
        with path.open(newline="", encoding="utf-8") as f:
            rows = csv.reader(f)
            for cols in rows:
                if len(cols) < 7:
                    continue
                academic_rows.append(
                    {
                        "code": cols[0],
                        "name": cols[1],
                        "L-T-P-C": cols[2],
                        "type": cols[3],
                        "faculty": cols[4],
                        "program": cols[5],
                        "semester": cols[-1],
                    }
                )

    with conn.cursor() as cur:
        cur.execute("DELETE FROM master_timetable")
        cur.execute("DELETE FROM conflict_report")
        cur.execute("DELETE FROM schedule_run")
        cur.execute("DELETE FROM batch_course_map")
        cur.execute("DELETE FROM faculty_course_map")
        cur.execute("DELETE FROM student_batch")
        cur.execute("DELETE FROM course")
        cur.execute("DELETE FROM faculty")

    faculty_ids: dict[str, int] = {}
    course_ids: dict[str, int] = {}
    batch_ids: dict[str, int] = {}

    def ensure_faculty(cur, short_name: str) -> int:
        key = _norm_faculty_key(short_name)
        if key in faculty_ids:
            return faculty_ids[key]
        cur.execute(
            """
            INSERT INTO faculty (short_name, full_name)
            VALUES (%s, %s)
            ON CONFLICT (short_name) DO UPDATE SET full_name = EXCLUDED.full_name
            RETURNING faculty_id
            """,
            (key, short_name),
        )
        fid = cur.fetchone()[0]
        faculty_ids[key] = fid
        return fid

    def ensure_course(cur, code: str, title: str, ltp: str, ctype: str) -> int:
        code = code.strip()
        if code in course_ids:
            return course_ids[code]
        lh, th, ph, cr = _parse_ltp(ltp)
        eslot = _elective_slot(ctype, code)
        cur.execute(
            """
            INSERT INTO course (code, title, lecture_hours, tutorial_hours, practical_hours, credits, course_type, elective_slot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING course_id
            """,
            (code, title, lh, th, ph, cr, ctype.strip(), eslot),
        )
        cid = cur.fetchone()[0]
        course_ids[code] = cid
        stats["courses"] += 1
        return cid

    def ensure_batch(cur, program: str, semester: int) -> int:
        bcode = f"{program.strip()}-S{semester}"
        if bcode in batch_ids:
            return batch_ids[bcode]
        cur.execute(
            """
            INSERT INTO student_batch (batch_code, program, semester, batch_size)
            VALUES (%s, %s, %s, %s)
            RETURNING batch_id
            """,
            (bcode, program.strip(), semester, default_batch_size),
        )
        bid = cur.fetchone()[0]
        batch_ids[bcode] = bid
        return bid

    with conn.cursor() as cur:
        for r in academic_rows:
            code = (r.get("code") or "").strip()
            if not code:
                continue
            name = (r.get("name") or "").strip()
            ltp = (r.get("L-T-P-C") or r.get("ltp") or "").strip()
            ctype = (r.get("type") or "").strip()
            fac = (r.get("faculty") or "").strip()
            prog = (r.get("program") or "").strip()
            sem_s = (r.get("semester") or "").strip()
            if not prog or not sem_s:
                continue
            try:
                semester = int(sem_s)
            except ValueError:
                continue

            lh, _, _, _ = _parse_ltp(ltp)
            if lh <= 0:
                stats["skipped_zero_lecture"] += 1
                continue

            fid = ensure_faculty(cur, fac)
            cid = ensure_course(cur, code, name, ltp, ctype)
            bid = ensure_batch(cur, prog, semester)

            cur.execute(
                """
                INSERT INTO faculty_course_map (faculty_id, course_id)
                VALUES (%s, %s)
                ON CONFLICT (faculty_id, course_id) DO NOTHING
                """,
                (fid, cid),
            )

            cur.execute(
                """
                INSERT INTO batch_course_map (batch_id, course_id, faculty_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (batch_id, course_id) DO UPDATE SET faculty_id = EXCLUDED.faculty_id
                """,
                (bid, cid, fid),
            )
            stats["rows"] += 1

    return stats


def load_assignment_map(
    conn: PgConnection, term: str | None = None
) -> list[dict[str, Any]]:
    """Load offerings for scheduling. ``term``: ``autumn`` | ``winter`` | ``all``/None."""
    extra = ""
    t = (term or "all").strip().lower()
    if t == "autumn":
        extra = " AND sb.semester IN (1, 3, 5)"
    elif t == "winter":
        extra = " AND sb.semester IN (2, 4, 6)"
    elif t not in ("all", ""):
        raise ValueError(f"Unknown term: {term!r} (use autumn, winter, or all)")

    return fetch_all(
        conn,
        f"""
        SELECT fcm.assignment_id, fcm.faculty_id, f.short_name AS faculty_short,
               c.course_id, c.code AS course_code, c.lecture_hours, c.course_type,
               c.elective_slot,
               bcm.batch_id, sb.batch_code, sb.batch_size, sb.program, sb.semester
        FROM batch_course_map bcm
        JOIN faculty_course_map fcm
          ON fcm.faculty_id = bcm.faculty_id AND fcm.course_id = bcm.course_id
        JOIN faculty f ON f.faculty_id = bcm.faculty_id
        JOIN course c ON c.course_id = bcm.course_id
        JOIN student_batch sb ON sb.batch_id = bcm.batch_id
        WHERE 1=1
        {extra}
        ORDER BY sb.program, sb.semester, c.code
        """,
    )
