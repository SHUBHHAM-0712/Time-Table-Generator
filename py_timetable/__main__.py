from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import db
from .csp_schedule import run_scheduler
from .export_views import export_excel, export_pdf_summary
from .ingest import get_default_batch_size, ingest_academic_csv, load_time_matrix


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_init_db(_a: argparse.Namespace) -> int:
    sql_dir = _root() / "sql"
    db.init_schema(sql_dir)
    print(f"Applied SQL from {sql_dir}")
    return 0


def _resolve_path(root: Path, p: str | Path) -> Path:
    path = Path(p)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def cmd_load(args: argparse.Namespace) -> int:
    root = _root()
    csv_path = _resolve_path(root, args.csv)
    conn = db.connect()
    try:
        if args.slots:
            slots_path = _resolve_path(root, args.slots)
            n = load_time_matrix(conn, slots_path)
            print(f"Replaced time_matrix with {n} rows from {slots_path.name}")
        else:
            print("Leaving time_matrix unchanged (seeded by init-db or load --slots).")
        bs = get_default_batch_size(conn)
        stats = ingest_academic_csv(conn, csv_path, bs)
        conn.commit()
        print(
            f"Ingested {stats['rows']} offerings; {stats['courses']} distinct course codes; "
            f"skipped L=0: {stats['skipped_zero_lecture']}"
        )
    finally:
        conn.close()
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        try:
            run_id, ok, msg = run_scheduler(
                conn,
                label=args.label,
                source_csv=args.source,
                timeout_seconds=float(args.timeout),
                term=args.term,
            )
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        conn.commit()
        print(msg)
        if ok:
            print(f"run_id={run_id}")
        return 0 if ok else 2
    finally:
        conn.close()


def cmd_export(args: argparse.Namespace) -> int:
    root = _root()
    out_dir = _resolve_path(root, args.out)
    conn = db.connect()
    try:
        paths = export_excel(conn, int(args.run_id), out_dir)
        pdf = export_pdf_summary(conn, int(args.run_id), out_dir)
        conn.commit()
        print("Excel:")
        for p in paths:
            print(f"  {p}")
        print(f"PDF summary: {pdf}")
    finally:
        conn.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit("Install uvicorn: pip install uvicorn[standard]") from e
    os.environ.setdefault("UVICORN_LOOP", "asyncio")
    uvicorn.run(
        "py_timetable.web.app:app",
        host=args.host,
        port=int(args.port),
        reload=args.reload,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Timetable generator — DB, CSP, exports")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init-db", help="Apply sql/###_*.sql files to DATABASE_URL")
    sp.set_defaults(func=cmd_init_db)

    sp = sub.add_parser(
        "load",
        help="Load academic offerings into PostgreSQL; time grid comes from DB unless --slots is set",
    )
    sp.add_argument(
        "--csv",
        required=True,
        help="Path to academic CSV (any path; columns: code,name,L-T-P-C,type,faculty,program,semester)",
    )
    sp.add_argument(
        "--slots",
        default=None,
        metavar="FILE",
        help="Optional: replace time_matrix from a grid CSV (omit to keep existing DB slots)",
    )
    sp.set_defaults(func=cmd_load)

    sp = sub.add_parser("schedule", help="Run CSP and fill master_timetable")
    sp.add_argument("--label", default="default", help="schedule_run label")
    sp.add_argument(
        "--source",
        default="db",
        help="Label stored on schedule_run (provenance note; default: db)",
    )
    sp.add_argument("--timeout", default="180", help="Seconds")
    sp.add_argument(
        "--term",
        default="all",
        metavar="T",
        help="Which semester cohort to schedule: autumn (1,3,5), winter (2,4,6), or all (default)",
    )
    sp.set_defaults(func=cmd_schedule)

    sp = sub.add_parser("export", help="Excel + PDF for a run_id")
    sp.add_argument("--run-id", required=True)
    sp.add_argument(
        "--out",
        default="output",
        help="Output directory (relative paths are under project root)",
    )
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("serve", help="Start minimal web UI (FastAPI)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", default="8000")
    sp.add_argument("--reload", action="store_true", help="Dev auto-reload")
    sp.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
