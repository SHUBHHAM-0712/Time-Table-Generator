from __future__ import annotations

import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, Route

ROOT = Path(__file__).resolve().parents[2]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    port = _find_free_port()
    env = os.environ.copy()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "py_timetable.web.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45.0
    err: str | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/", timeout=2) as r:
                if r.status == 200:
                    break
        except (OSError, urllib.error.URLError) as e:
            err = str(e)
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else b""
                proc.stderr.close() if proc.stderr else None
                raise RuntimeError(f"uvicorn exited: {stderr.decode()!r}") from e
            time.sleep(0.15)
    else:
        proc.terminate()
        if proc.stderr:
            err = proc.stderr.read().decode() or err
        raise RuntimeError(f"server failed to start: {err}")
    try:
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


SAMPLE_RUNS: list[dict[str, Any]] = [
    {
        "run_id": 1,
        "label": "web",
        "source_csv": "db",
        "status": "completed",
        "notes": "ok",
        "created_at": "2024-01-15T10:00:00",
    }
]
SAMPLE_META: dict[str, int] = {
    "faculty": 2,
    "course": 3,
    "student_batch": 4,
    "room": 5,
    "time_slot": 6,
    "batch_course_map": 7,
}

def _minimal_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("export.txt", b"mock")
    return buf.getvalue()


MINIMAL_ZIP_BYTES = _minimal_zip_bytes()

SAMPLE_EVENTS: list[dict[str, Any]] = [
    {
        "day_of_week": "Mon",
        "start_time": "09:00:00",
        "end_time": "10:00:00",
        "batch_code": "ICT-S3-A",
        "faculty": "FAC-A",
        "room_code": "R-101",
        "course_code": "CS201",
    },
    {
        "day_of_week": "Tue",
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "batch_code": "ICT-S3-B",
        "faculty": "FAC-B",
        "room_code": "R-102",
        "course_code": "CS202",
    },
]


def install_api_mocks(
    page: Page,
    *,
    runs: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
    events_by_run: dict[int, list[dict[str, Any]]] | None = None,
    conflicts_by_run: dict[int, list[dict[str, Any]]] | None = None,
    load_body: str | None = None,
    schedule_body: str | None = None,
    schedule_status: int = 200,
    health_status: int = 200,
    health_body: str | None = None,
    mock_export_zip: bool = True,
) -> None:
    # Allow repeated installs in a single test (e.g. different mock for Refresh).
    page.unroute("**/*")
    r_json = json.dumps(runs if runs is not None else SAMPLE_RUNS)
    m_json = json.dumps(meta if meta is not None else SAMPLE_META)
    evmap = events_by_run if events_by_run is not None else {1: SAMPLE_EVENTS}
    confmap: dict[int, list[dict[str, Any]]] = conflicts_by_run if conflicts_by_run is not None else {}
    load_b = load_body or '{"ok": true, "message": "ok"}'
    sched_b = schedule_body or '{"ok": true, "run_id": 2, "message": "ok"}'
    health_b = health_body or '{"ok": false, "error": "mock"}'
    re_events = re.compile(r"/api/run/(\d+)/events$")
    re_conf = re.compile(r"/api/run/(\d+)/conflicts$")
    re_zip = re.compile(r"/api/export/(\d+)/zip$")

    def handle(route: Route) -> None:
        req = route.request
        p = str(req.url)
        if "/api/" not in p:
            route.continue_()
            return
        path = urlparse(p).path
        if path == "/api/health" and req.method == "GET":
            route.fulfill(
                status=health_status,
                content_type="application/json",
                body='{"ok": true, "database": "connected"}' if health_status == 200 else health_b,
            )
            return
        if path == "/api/meta" and req.method == "GET":
            route.fulfill(status=200, content_type="application/json", body=m_json)
            return
        if path == "/api/runs" and req.method == "GET":
            route.fulfill(status=200, content_type="application/json", body=r_json)
            return
        if path == "/api/load" and req.method == "POST":
            route.fulfill(status=200, content_type="application/json", body=load_b)
            return
        if path == "/api/schedule" and req.method == "POST":
            route.fulfill(
                status=schedule_status,
                content_type="application/json",
                body=sched_b,
            )
            return
        if mock_export_zip and re_zip.search(path) and req.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/zip",
                body=MINIMAL_ZIP_BYTES,
                headers={"Content-Disposition": 'attachment; filename="timetable_run1.zip"'},
            )
            return
        m = re_events.search(path)
        if m and req.method == "GET":
            rid = int(m.group(1))
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(evmap.get(rid, [])),
            )
            return
        m2 = re_conf.search(path)
        if m2 and req.method == "GET":
            rid = int(m2.group(1))
            body = json.dumps(confmap.get(rid, []))
            route.fulfill(status=200, content_type="application/json", body=body)
            return
        route.fulfill(status=404, content_type="application/json", body="{}")
        return

    page.route("**/*", handle)
