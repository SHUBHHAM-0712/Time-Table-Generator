from __future__ import annotations

from pathlib import Path
from typing import Any

from psycopg2.extensions import connection as PgConnection
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from .db import fetch_all


def fetch_timetable_events(conn: PgConnection, run_id: int) -> list[dict[str, Any]]:
    """All scheduled rows for a run (for UI / JSON export).

    Expands merged timetable rows so each batch in a merged group appears
    as its own event. Returns one dict per (timetable row, actual batch).
    """
    return _fetch_events(conn, run_id)


def _fetch_events(conn: PgConnection, run_id: int) -> list[dict[str, Any]]:
    # Fetch raw timetable rows including merge metadata
    rows = fetch_all(
        conn,
        """
        SELECT
            mt.timetable_id,
            mt.batch_id as rep_batch_id,
            mt.merged_batch_ids,
            COALESCE(mt.is_merged, FALSE) as is_merged,
            tm.day_of_week,
            tm.start_time,
            tm.end_time,
            c.code AS course_code,
            c.title AS course_title,
            f.short_name AS faculty,
            r.room_code,
            r.capacity
        FROM master_timetable mt
        JOIN time_matrix tm ON tm.slot_id = mt.slot_id
        JOIN faculty_course_map fcm ON fcm.assignment_id = mt.assignment_id
        JOIN faculty f ON f.faculty_id = fcm.faculty_id
        JOIN course c ON c.course_id = fcm.course_id
        JOIN room r ON r.room_id = mt.room_id
        WHERE mt.run_id = %s
        ORDER BY tm.day_of_week, tm.start_time
        """,
        (run_id,),
    )

    # Build a map of batch_id -> student_batch info for quick lookup
    batch_ids = set()
    for r in rows:
        # representative batch
        if r.get("rep_batch_id"):
            batch_ids.add(int(r["rep_batch_id"]))
        # merged batches (comma-separated)
        mb = r.get("merged_batch_ids")
        if mb:
            for bid in str(mb).split(","):
                bid = bid.strip()
                if bid:
                    batch_ids.add(int(bid))

    batches = {}
    if batch_ids:
        q = fetch_all(
            conn,
            "SELECT batch_id, batch_code, program, semester, batch_size FROM student_batch WHERE batch_id = ANY(%s)",
            (list(batch_ids),),
        )
        for b in q:
            batches[int(b["batch_id"])] = {
                "batch_code": b["batch_code"],
                "program": b["program"],
                "semester": b["semester"],
                "batch_size": b.get("batch_size"),
            }

    # Expand rows: for merged entries, yield one event per actual batch id
    events: list[dict[str, Any]] = []
    for r in rows:
        merged = bool(r.get("is_merged"))
        mb = r.get("merged_batch_ids")
        if merged and mb:
            ids = [int(x.strip()) for x in str(mb).split(",") if x.strip()]
            for bid in ids:
                info = batches.get(bid, {})
                ev = {
                    "timetable_id": r["timetable_id"],
                    "day_of_week": r["day_of_week"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "course_code": r["course_code"],
                    "course_title": r["course_title"],
                    "faculty": r["faculty"],
                    "batch_id": bid,
                    "batch_code": info.get("batch_code", f"B{bid}"),
                    "program": info.get("program"),
                    "semester": info.get("semester"),
                    "room_code": r["room_code"],
                    "capacity": r.get("capacity"),
                }
                events.append(ev)
        else:
            # single (non-merged) or merged with no metadata: use rep_batch_id
            bid = int(r.get("rep_batch_id")) if r.get("rep_batch_id") is not None else None
            info = batches.get(bid, {}) if bid is not None else {}
            ev = {
                "timetable_id": r["timetable_id"],
                "day_of_week": r["day_of_week"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "course_code": r["course_code"],
                "course_title": r["course_title"],
                "faculty": r["faculty"],
                "batch_id": bid,
                "batch_code": info.get("batch_code", f"B{bid}"),
                "program": info.get("program"),
                "semester": info.get("semester"),
                "room_code": r["room_code"],
                "capacity": r.get("capacity"),
            }
            events.append(ev)

    # Sort events for consistent output
    events.sort(key=lambda x: (x.get("batch_code"), x.get("day_of_week"), str(x.get("start_time"))))
    return events


def _day_order() -> dict[str, int]:
    return {"Mon": 0, "Tue": 1, "Wed": 2, "Thur": 3, "Fri": 4}


def _sheet_name(name: str) -> str:
    bad = set("[]:*?/\\")
    safe = "".join(c if c not in bad else "_" for c in name)[:31]
    return safe or "Sheet"


def export_excel(conn: PgConnection, run_id: int, out_dir: Path) -> list[Path]:
    try:
        import pandas as pd
    except ImportError as e:
        raise RuntimeError("openpyxl/pandas required for Excel export") from e

    out_dir.mkdir(parents=True, exist_ok=True)
    events = fetch_timetable_events(conn, run_id)
    if not events:
        raise RuntimeError(f"No timetable rows for run_id={run_id}")

    paths: list[Path] = []
    days = ["Mon", "Tue", "Wed", "Thur", "Fri"]

    # Master by batch
    batches = sorted({str(e["batch_code"]) for e in events})
    for bc in batches:
        sub = [e for e in events if str(e["batch_code"]) == bc]
        times = sorted(
            {(str(e["start_time"])[:5], str(e["end_time"])[:5]) for e in sub},
            key=lambda x: x[0],
        )
        rows_out: list[dict[str, Any]] = []
        for t0, t1 in times:
            row: dict[str, Any] = {"time": f"{t0}-{t1}"}
            for d in days:
                cell = ""
                for e in sub:
                    if (
                        str(e["day_of_week"]) == d
                        and str(e["start_time"])[:5] == t0
                    ):
                        cell = (
                            f"{e['course_code']} | {e['faculty']} | {e['room_code']}"
                        )
                        break
                row[d] = cell
            rows_out.append(row)
        df = pd.DataFrame(rows_out)
        p = out_dir / f"master_batch_{bc}_run{run_id}.xlsx"
        df.to_excel(p, index=False)
        paths.append(p)

    # Faculty sheets (one file)
    fac_set = sorted({str(e["faculty"]) for e in events})
    with pd.ExcelWriter(out_dir / f"faculty_timetables_run{run_id}.xlsx", engine="openpyxl") as xw:
        for fac in fac_set:
            sub = [e for e in events if str(e["faculty"]) == fac]
            times = sorted(
                {(str(e["start_time"])[:5], str(e["end_time"])[:5]) for e in sub},
                key=lambda x: x[0],
            )
            rows_out = []
            for t0, t1 in times:
                row: dict[str, Any] = {"time": f"{t0}-{t1}"}
                for d in days:
                    cell = ""
                    for e in sub:
                        if (
                            str(e["day_of_week"]) == d
                            and str(e["start_time"])[:5] == t0
                        ):
                            cell = f"{e['course_code']} | {e['batch_code']} | {e['room_code']}"
                            break
                    row[d] = cell
                rows_out.append(row)
            pd.DataFrame(rows_out).to_excel(xw, sheet_name=_sheet_name(fac), index=False)

    paths.append(out_dir / f"faculty_timetables_run{run_id}.xlsx")

    # Room utilization
    rooms = sorted({str(e["room_code"]) for e in events})
    with pd.ExcelWriter(out_dir / f"room_utilization_run{run_id}.xlsx", engine="openpyxl") as xw:
        for rm in rooms:
            sub = [e for e in events if str(e["room_code"]) == rm]
            times = sorted(
                {(str(e["start_time"])[:5], str(e["end_time"])[:5]) for e in sub},
                key=lambda x: x[0],
            )
            rows_out = []
            for t0, t1 in times:
                row: dict[str, Any] = {"time": f"{t0}-{t1}"}
                for d in days:
                    cell = ""
                    for e in sub:
                        if (
                            str(e["day_of_week"]) == d
                            and str(e["start_time"])[:5] == t0
                        ):
                            cell = f"{e['course_code']} | {e['batch_code']} | {e['faculty']}"
                            break
                    row[d] = cell
                rows_out.append(row)
            pd.DataFrame(rows_out).to_excel(xw, sheet_name=_sheet_name(rm), index=False)

    paths.append(out_dir / f"room_utilization_run{run_id}.xlsx")

    return paths


def export_pdf_summary(conn: PgConnection, run_id: int, out_dir: Path) -> Path:
    events = fetch_timetable_events(conn, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"master_summary_run{run_id}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4))
    data = [["Day", "Time", "Batch", "Course", "Faculty", "Room"]]
    order = _day_order()
    for e in sorted(
        events,
        key=lambda x: (order.get(str(x["day_of_week"]), 9), str(x["start_time"]), str(x["batch_code"])),
    ):
        data.append(
            [
                str(e["day_of_week"]),
                f"{str(e['start_time'])[:5]}-{str(e['end_time'])[:5]}",
                str(e["batch_code"]),
                str(e["course_code"]),
                str(e["faculty"]),
                str(e["room_code"]),
            ]
        )
    t = Table(data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]
        )
    )
    doc.build([t])
    return path
