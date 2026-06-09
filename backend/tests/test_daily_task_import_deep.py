"""daily_task_import 補測：_parse_row 各驗證分支（單元）+ import/excel 端點 error 分支。"""

import io

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

from app.api.v1.endpoints.daily_task_import import _parse_row


class _Cell:
    def __init__(self, value):
        self.value = value


def _row(*values):
    return tuple(_Cell(v) for v in values)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── _parse_row 純函式分支 ───────────────────────────────────────
def test_parse_row_empty_title():
    res = _parse_row(_row("", "2026-06-03"), 2)
    assert isinstance(res, str)
    assert "標題" in res


def test_parse_row_bad_date_format():
    res = _parse_row(_row("Task", "not-a-date"), 2)
    assert isinstance(res, str)
    assert "日期格式" in res


def test_parse_row_empty_date():
    res = _parse_row(_row("Task", None), 2)
    assert isinstance(res, str)
    assert "日期" in res


def test_parse_row_string_date_ok():
    res = _parse_row(_row("Task", "2026-06-03", "完成", 100, "開發, 會議", "desc", 30), 2)
    assert isinstance(res, dict)
    assert res["title"] == "Task"
    assert res["status"] == "done"
    assert res["progress"] == 100
    assert res["labels"] == ["開發", "會議"]
    assert res["work_minutes"] == 30


def test_parse_row_non_numeric_progress_and_minutes_default_zero():
    res = _parse_row(_row("Task", "2026-06-03", "待辦", "abc", "", "", "xyz"), 2)
    assert isinstance(res, dict)
    assert res["progress"] == 0
    assert res["work_minutes"] == 0


def test_parse_row_progress_clamped():
    res = _parse_row(_row("Task", "2026-06-03", "進行中", 500), 2)
    assert res["progress"] == 100


def test_parse_row_datetime_object_date():
    from datetime import datetime

    res = _parse_row(_row("Task", datetime(2026, 6, 3, 9, 0)), 2)
    assert isinstance(res, dict)
    assert res["date"].isoformat() == "2026-06-03"


# ── import/excel 端點 error 分支 ────────────────────────────────
@pytest.mark.asyncio
async def test_import_rejects_non_xlsx(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={"file": ("data.csv", b"a,b", "text/csv")},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_rejects_unparseable_xlsx(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={
            "file": (
                "bad.xlsx",
                b"not really xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_success_with_mixed_rows(client: AsyncClient, admin_token: str):
    # build a real xlsx: one valid row, one invalid (empty title)
    wb = Workbook()
    ws = wb.active
    ws.append(["標題", "日期", "狀態", "進度", "標籤", "說明", "工時"])  # header
    ws.append(["Valid Task", "2026-06-03", "完成", 80, "開發", "ok", 25])
    ws.append(["", "2026-06-03", "待辦", 0, "", "", 0])  # invalid: empty title
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={
            "file": (
                "data.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1


@pytest.mark.asyncio
async def test_import_empty_sheet(client: AsyncClient, admin_token: str):
    wb = Workbook()
    ws = wb.active
    ws.append(["標題", "日期"])  # header only, no data rows
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={
            "file": (
                "empty.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_download_template(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/daily-tasks/import/template", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
