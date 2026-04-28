from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from .conftest import SAMPLE_RUNS, install_api_mocks

pytestmark = pytest.mark.e2e


def test_landing_page_structure(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    expect(page.locator("h1")).to_have_text("Timetable Generator")
    expect(page.get_by_role("heading", name="Replace catalog from CSV (optional)")).to_be_visible()
    expect(page.get_by_role("heading", name="Generate schedule")).to_be_visible()
    expect(page.get_by_role("heading", name="Runs")).to_be_visible()
    expect(page.locator("#form-load")).to_be_visible()
    expect(page.locator("#form-schedule")).to_be_visible()
    expect(page.locator("#btn-refresh-runs")).to_be_visible()
    expect(page.locator("link[href='/static/style.css']")).to_be_attached()


def test_db_status_and_meta_with_mocks(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    expect(page.locator("#db-status")).to_contain_text("Database connected.", timeout=10_000)
    meta = page.locator("#meta")
    expect(meta).to_contain_text("Faculty")
    expect(meta).to_contain_text("2")
    expect(meta).to_contain_text("Enrollments")


def test_runs_table_populated_with_actions(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    row = page.locator("#runs-table tbody tr").first
    expect(row).to_contain_text("1")
    expect(row).to_contain_text("web")
    expect(row).to_contain_text("completed")
    expect(row.get_by_role("button", name="Preview")).to_be_visible()
    expect(row.get_by_role("button", name="ZIP")).to_be_visible()


def test_refresh_runs_reloads_table(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        runs=[
            {**SAMPLE_RUNS[0], "label": "first"},
        ],
    )
    page.goto(e2e_base_url + "/")
    expect(page.locator("#runs-table")).to_contain_text("first")
    install_api_mocks(
        page,
        runs=[
            {**SAMPLE_RUNS[0], "run_id": 2, "label": "refreshed"},
        ],
    )
    page.locator("#btn-refresh-runs").click()
    expect(page.locator("#runs-table")).to_contain_text("refreshed", timeout=10_000)
    expect(page.locator("#runs-table")).to_contain_text("2")


def test_load_form_displays_api_json(page: Page, e2e_base_url: str) -> None:
    body = json.dumps(
        {
            "ok": True,
            "rows": 10,
            "courses": 3,
            "slots": "time_matrix unchanged.",
        }
    )
    install_api_mocks(
        page,
        load_body=body,
    )
    page.goto(e2e_base_url + "/")
    page.locator("#form-load").evaluate("f => f.requestSubmit()")
    out = page.locator("#load-out")
    expect(out).to_be_visible()
    expect(out).to_contain_text("rows", timeout=10_000)
    expect(out).to_contain_text("10")


def test_schedule_form_shows_result_and_re_enables(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        schedule_body=json.dumps({"ok": True, "run_id": 7, "message": "ok"}),
    )
    page.goto(e2e_base_url + "/")
    btn = page.locator("#btn-schedule")
    expect(btn).to_be_enabled()
    page.locator("#form-schedule").evaluate("f => f.requestSubmit()")
    expect(page.locator("#schedule-out")).to_contain_text("run_id", timeout=20_000)
    expect(page.locator("#schedule-out")).to_contain_text("7")
    expect(page.locator("#schedule-banner")).to_be_hidden()
    expect(btn).to_be_enabled()


def test_preview_shows_timetable_tabs(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    page.locator("#runs-table").get_by_role("button", name="Preview").first.click()
    expect(page.locator("#preview-section")).to_be_visible()
    expect(page.locator("#preview-tabs").get_by_role("button", name="By batch")).to_be_visible()
    expect(page.locator("#preview-table table.data")).to_be_visible(timeout=10_000)
    expect(page.locator("#preview-table")).to_contain_text("CS201")


def test_preview_empty_with_conflicts_shows_json(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        events_by_run={1: []},
        conflicts_by_run={1: [{"report_id": 1, "severity": "err", "category": "c", "detail": "d"}]},
    )
    page.goto(e2e_base_url + "/")
    page.locator("#runs-table").get_by_role("button", name="Preview").first.click()
    cf = page.locator("#preview-conflicts")
    expect(cf).to_be_visible(timeout=10_000)
    expect(cf).to_contain_text("report_id")
