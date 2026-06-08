import io

import pytest
from httpx import AsyncClient
from openpyxl import Workbook


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_xlsx(rows):
    """Build an in-memory .xlsx with header row + given data rows."""
    wb = Workbook()
    ws = wb.active
    ws.append(["標題", "日期", "狀態", "進度%", "標籤", "說明", "工作分鐘數"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_download_template(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/daily-tasks/import/template", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_import_excel_success(client: AsyncClient, admin_token: str):
    buf = _make_xlsx(
        [
            ["匯入任務A", "2026-06-10", "完成", 100, "開發", "說明", 30],
            ["匯入任務B", "2026-06-11", "進行中", 50, "", "", 0],
        ]
    )
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={"file": ("import.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_import_excel_with_errors(client: AsyncClient, admin_token: str):
    buf = _make_xlsx(
        [
            ["", "2026-06-10", "完成", 100, "", "", 0],  # missing title
            ["有效任務", "not-a-date", "完成", 100, "", "", 0],  # bad date
            ["好任務", "2026-06-12", "待辦", 0, "", "", 0],  # valid
        ]
    )
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={"file": ("import.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 2


@pytest.mark.asyncio
async def test_import_rejects_non_xlsx(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/daily-tasks/import/excel",
        files={"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
