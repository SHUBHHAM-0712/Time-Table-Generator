from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from .conftest import SAMPLE_RUNS, install_api_mocks

pytestmark = pytest.mark.e2e


def test_landing_page_structure(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    expect(page.locator("h1")).to_have_text("OptiSchedule")
    expect(page.locator(".navbar-brand p")).to_have_text("Timetable Generator")
    expect(page.get_by_role("heading", name="Academic Schedule Management")).to_be_visible()
    expect(page.get_by_role("heading", name="Data Ingest")).to_be_visible()
    expect(page.get_by_role("heading", name="Generate Schedule")).to_be_visible()
    expect(page.get_by_role("heading", name="Runs")).to_be_visible()
    expect(page.locator("#form-load")).to_be_visible()
    expect(page.locator("#form-schedule")).to_be_visible()
    expect(page.locator("#btn-refresh-runs")).to_be_visible()
    expect(page.locator("link[href='/static/style.css']")).to_be_attached()
    expect(page.locator("link[rel='preconnect'][href='https://fonts.googleapis.com']")).to_be_attached()
    expect(
        page.locator("link[rel='stylesheet'][href*='fonts.googleapis.com/css2']")
    ).to_be_attached()
    expect(page.locator("link[rel='icon']")).to_have_attribute("href", "/static/tt-fevicon.png")


def test_static_style_css_served(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    res = page.request.get(e2e_base_url + "/static/style.css")
    assert res.ok
    assert res.status == 200
    assert "text/css" in (res.headers.get("content-type") or "")


def test_db_status_ok_with_mocks(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    expect(page.locator("#db-status")).to_contain_text("Database OK", timeout=10_000)
    expect(page.locator("#db-status.ok")).to_be_visible()


def test_db_status_error_when_health_not_ok(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page, health_status=503, health_body='{"ok": false, "error": "down"}')
    page.goto(e2e_base_url + "/")
    expect(page.locator("#db-status")).to_contain_text("Database down", timeout=10_000)
    expect(page.locator("#db-status.error")).to_be_visible()


def test_metrics_cards_populated(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    meta = page.locator("#meta")
    expect(meta.locator(".metric-card").first).to_be_visible(timeout=10_000)
    expect(meta).to_contain_text("Faculty")
    expect(meta.locator(".metric-value").first).to_contain_text("2")
    expect(meta).to_contain_text("Enrollments")


def test_runs_table_rows_and_actions(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    row = page.locator("#runs-table tbody tr").first
    expect(row.locator(".run-id")).to_have_text("1")
    expect(row).to_contain_text("web")
    expect(row.locator(".status-badge")).to_contain_text("completed")
    expect(row.get_by_role("button", name="Preview")).to_be_visible()
    expect(row.get_by_role("button", name="ZIP")).to_be_visible()


def test_run_status_badge_success_style(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        runs=[{**SAMPLE_RUNS[0], "status": "success"}],
    )
    page.goto(e2e_base_url + "/")
    expect(page.locator(".status-badge.status-success")).to_have_text("success")


def test_run_status_badge_error_style(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        runs=[{**SAMPLE_RUNS[0], "status": "error"}],
    )
    page.goto(e2e_base_url + "/")
    expect(page.locator(".status-badge.status-error")).to_have_text("error")


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
    expect(page.locator("#runs-table .run-id").first).to_have_text("2")


def test_load_form_displays_api_json(page: Page, e2e_base_url: str) -> None:
    body = json.dumps(
        {
            "ok": True,
            "rows": 10,
            "courses": 3,
            "slots": "time_matrix unchanged.",
        }
    )
    install_api_mocks(page, load_body=body)
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


def test_schedule_form_shows_http_error_detail(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        schedule_status=400,
        schedule_body=json.dumps({"detail": "Unknown term"}),
    )
    page.goto(e2e_base_url + "/")
    page.locator("#form-schedule").evaluate("f => f.requestSubmit()")
    out = page.locator("#schedule-out")
    expect(out).to_contain_text("HTTP 400", timeout=20_000)
    expect(out).to_contain_text("Unknown term")


def test_schedule_term_winter_submitted(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(
        page,
        schedule_body=json.dumps({"ok": True, "run_id": 1, "message": "ok"}),
    )
    page.goto(e2e_base_url + "/")
    page.locator("#schedule-term").select_option("winter")
    with page.expect_request(
        lambda r: r.method == "POST" and r.url.rstrip("/").endswith("/api/schedule")
    ) as req_info:
        page.locator("#form-schedule").evaluate("f => f.requestSubmit()")
    post = req_info.value.post_data or ""
    assert 'name="term"' in post and "winter" in post
    expect(page.locator("#schedule-out")).to_contain_text("run_id", timeout=20_000)


def test_preview_shows_timetable_and_batch_tab(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    page.locator("#runs-table").get_by_role("button", name="Preview").first.click()
    expect(page.locator("#preview-section")).to_be_visible()
    expect(page.locator("#preview-tabs").get_by_role("button", name="By Batch")).to_be_visible()
    expect(page.locator("#preview-table table.schedule-table")).to_be_visible(timeout=10_000)
    expect(page.locator("#preview-table .schedule-event").first).to_contain_text("CS201")


def test_preview_switch_to_faculty_and_subtab(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    page.locator("#runs-table").get_by_role("button", name="Preview").first.click()
    expect(page.locator("#preview-subtabs")).to_be_visible(timeout=10_000)
    page.locator("#preview-tabs").get_by_role("button", name="By Faculty").click()
    page.locator("#preview-subtabs").get_by_role("button", name="FAC-B").click()
    expect(page.locator("#preview-table")).to_contain_text("CS202")


def test_preview_switch_to_room_tab(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    page.locator("#runs-table").get_by_role("button", name="Preview").first.click()
    page.locator("#preview-tabs").get_by_role("button", name="By Room").click()
    page.locator("#preview-subtabs").get_by_role("button", name="R-101").click()
    expect(page.locator("#preview-table")).to_contain_text("CS201")


def test_preview_empty_no_conflicts_message(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page, events_by_run={1: []}, conflicts_by_run={1: []})
    page.goto(e2e_base_url + "/")
    page.locator("#runs-table").get_by_role("button", name="Preview").first.click()
    expect(page.locator("#preview-table")).to_contain_text(
        "No timetable rows", timeout=10_000
    )
    expect(page.locator("#preview-conflicts")).to_be_hidden()


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


def test_zip_button_triggers_export_request(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    with page.expect_request(lambda r: "/api/export/1/zip" in r.url) as req_info:
        page.locator("#runs-table tbody tr").first.get_by_role("button", name="ZIP").click()
    assert req_info.value.method == "GET"


def test_schedule_running_banner_dom_and_hides_after_success(page: Page, e2e_base_url: str) -> None:
    """Banner markup is present; after a successful run it ends hidden (CSS respects [hidden])."""
    install_api_mocks(
        page,
        schedule_body=json.dumps({"ok": True, "run_id": 1, "message": "ok"}),
    )
    page.goto(e2e_base_url + "/")
    banner = page.locator("#schedule-banner")
    expect(banner.locator(".banner-title")).to_contain_text("Scheduler Running")
    page.locator("#form-schedule").evaluate("f => f.requestSubmit()")
    expect(page.locator("#schedule-out")).to_contain_text("run_id", timeout=20_000)
    expect(banner).to_be_hidden()


def test_label_and_timeout_fields_editable(page: Page, e2e_base_url: str) -> None:
    install_api_mocks(page)
    page.goto(e2e_base_url + "/")
    page.locator("#schedule-label").fill("my-label")
    page.locator("#schedule-timeout").fill("240")
    expect(page.locator("#schedule-label")).to_have_value("my-label")
    expect(page.locator("#schedule-timeout")).to_have_value("240")
