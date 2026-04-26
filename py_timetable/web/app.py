from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import psycopg2
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db
from ..csp_schedule import run_scheduler
from ..export_views import export_excel, export_pdf_summary, fetch_timetable_events
from ..ingest import get_default_batch_size, ingest_academic_csv, load_time_matrix

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Timetable Generator", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _conn():
    return db.connect()


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
        elif hasattr(v, "isoformat"):
            out[k] = str(v)
        else:
            out[k] = v
    return out


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Any:
    # Starlette 1.x / current FastAPI: request must be the first argument
    return _TEMPLATES.TemplateResponse(request, "index.html", {})


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    try:
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return {"ok": True, "database": "connected"}
        finally:
            conn.close()
    except (RuntimeError, ValueError, OSError, psycopg2.Error) as e:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": str(e)},
        )


@app.get("/api/meta")
def api_meta() -> dict[str, Any]:
    conn = _conn()
    try:
        def c(table: str) -> int:
            r = db.fetch_one(conn, f"SELECT count(*)::int AS n FROM {table}")
            return int(r["n"]) if r else 0

        return {
            "faculty": c("faculty"),
            "course": c("course"),
            "student_batch": c("student_batch"),
            "room": c("room"),
            "time_slot": c("time_matrix"),
            "batch_course_map": c("batch_course_map"),
        }
    finally:
        conn.close()


@app.get("/api/runs")
def api_runs() -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = db.fetch_all(
            conn,
            """
            SELECT run_id, label, source_csv, status, notes, created_at
            FROM schedule_run
            ORDER BY run_id DESC
            LIMIT 50
            """,
        )
        return [_serialize_row(dict(r)) for r in rows]
    finally:
        conn.close()


@app.get("/api/run/{run_id}/events")
def api_run_events(run_id: int) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        events = fetch_timetable_events(conn, run_id)
        return [_serialize_row(dict(e)) for e in events]
    finally:
        conn.close()


@app.get("/api/run/{run_id}/conflicts")
def api_run_conflicts(run_id: int) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = db.fetch_all(
            conn,
            """
            SELECT report_id, severity, category, detail, created_at
            FROM conflict_report
            WHERE run_id = %s
            ORDER BY report_id
            """,
            (run_id,),
        )
        return [_serialize_row(dict(r)) for r in rows]
    finally:
        conn.close()


@app.post("/api/load")
async def api_load(
    academic: UploadFile | None = File(default=None),
    slots: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    path_ac: str | None = None
    if academic and getattr(academic, "filename", None):
        suffix = Path(academic.filename or "data.csv").suffix or ".csv"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="ttg_ac_") as tmp:
            tmp.write(await academic.read())
            path_ac = tmp.name
    try:
        conn = _conn()
        try:
            msg_slots = "time_matrix unchanged."
            if slots and getattr(slots, "filename", None):
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=Path(slots.filename or "slots").suffix or ".csv",
                    prefix="ttg_sl_",
                ) as tmp_sl:
                    tmp_sl.write(await slots.read())
                    path_sl = tmp_sl.name
                try:
                    n = load_time_matrix(conn, Path(path_sl))
                    msg_slots = f"Replaced time_matrix ({n} rows)."
                finally:
                    Path(path_sl).unlink(missing_ok=True)
            if not path_ac:
                conn.commit()
                return {
                    "ok": True,
                    "message": "No academic CSV uploaded; offerings unchanged.",
                    "slots": msg_slots,
                }
            bs = get_default_batch_size(conn)
            stats = ingest_academic_csv(conn, Path(path_ac), bs)
            conn.commit()
            return {
                "ok": True,
                "slots": msg_slots,
                "rows": stats["rows"],
                "courses": stats["courses"],
                "skipped_zero_lecture": stats["skipped_zero_lecture"],
            }
        finally:
            conn.close()
    finally:
        if path_ac:
            Path(path_ac).unlink(missing_ok=True)


@app.post("/api/schedule")
def api_schedule(
    label: str = Form("web"),
    source: str = Form("db"),
    timeout: float = Form(180),
    term: str = Form("all"),
) -> dict[str, Any]:
    conn = None
    try:
        conn = _conn()
        try:
            run_id, ok, msg = run_scheduler(
                conn,
                label=label,
                source_csv=source,
                timeout_seconds=timeout,
                term=term.strip() or "all",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        conn.commit()
        return {"ok": ok, "run_id": run_id, "message": msg}
    except (RuntimeError, psycopg2.Error) as e:
        # Keep API responses JSON so the frontend can show useful error details.
        raise HTTPException(status_code=500, detail=f"Scheduler failed: {e}") from e
    finally:
        if conn is not None:
            conn.close()


@app.get("/api/schedule")
def api_schedule_help() -> dict[str, Any]:
    return {
        "ok": False,
        "hint": "Use POST /api/schedule with form fields: label, source, timeout, term",
        "example": {
            "label": "web",
            "source": "db",
            "timeout": 180,
            "term": "all",
        },
    }


@app.get("/api/shedule")
def api_schedule_typo_help() -> dict[str, Any]:
    return {
        "ok": False,
        "hint": "Endpoint name is /api/schedule (not /api/shedule). Use POST /api/schedule.",
    }


@app.get("/api/export/{run_id}/zip")
def api_export_zip(run_id: int) -> StreamingResponse:
    conn = _conn()
    try:
        with tempfile.TemporaryDirectory(dir=_PROJECT_ROOT) as td:
            out = Path(td)
            paths = export_excel(conn, run_id, out)
            pdf = export_pdf_summary(conn, run_id, out)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    zf.write(p, arcname=p.name)
                zf.write(pdf, arcname=pdf.name)
            buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="timetable_run{run_id}.zip"',
            },
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        conn.close()

