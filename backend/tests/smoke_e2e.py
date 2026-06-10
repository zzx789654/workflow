"""WorkFlow 實地部署端到端煙霧測試（against running HTTPS deployment）。

針對已部署的 nginx HTTPS 入口逐功能打 API，串接 token / 資源 ID，
驗證任務核心環 + 協作 + 輔助功能。每步記 PASS/FAIL，最後印通過率。

用法（在部署主機上）：
  HOME=/opt/workflow .venv/bin/python tests/smoke_e2e.py \
    --base https://localhost --admin-pass '<admin_password>'
"""

import argparse
import datetime
import sys
import uuid

import httpx

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not cond else ""))
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://localhost")
    ap.add_argument("--admin-pass", required=True)
    ap.add_argument("--admin-user", default="admin")
    args = ap.parse_args()

    c = httpx.Client(base_url=args.base, verify=False, timeout=15.0)
    api = "/api/v1"

    # ── 1. 健康檢查 ──────────────────────────────────────────
    r = c.get("/health")
    check("health endpoint", r.status_code == 200 and r.json().get("status") == "ok", r.text)

    # ── 2. 認證：admin 登入 ──────────────────────────────────
    r = c.post(f"{api}/auth/login", json={"username": args.admin_user, "password": args.admin_pass})
    ok = check("admin login", r.status_code == 200 and "access_token" in r.json(), r.text)
    if not ok:
        summarize(); sys.exit(1)
    tok = r.json()["access_token"]
    refresh = r.json().get("refresh_token")
    H = {"Authorization": f"Bearer {tok}"}

    # 錯誤密碼應 401
    r = c.post(f"{api}/auth/login", json={"username": args.admin_user, "password": "wrong_password_xx"})
    check("login wrong password rejected (401)", r.status_code == 401, r.text)

    # refresh token（refresh_token 走 query 參數）
    if refresh:
        r = c.post(f"{api}/auth/refresh", params={"refresh_token": refresh})
        check("token refresh", r.status_code == 200 and "access_token" in r.json(), r.text)

    # ── 3. 使用者 ────────────────────────────────────────────
    r = c.get(f"{api}/users/me", headers=H)
    check("get current user (/users/me)", r.status_code == 200 and r.json().get("username") == args.admin_user, r.text)
    r = c.get(f"{api}/users/", headers=H)
    check("list users", r.status_code == 200 and isinstance(r.json(), list), r.text)

    # 未授權存取應 401
    r = c.get(f"{api}/users/me")
    check("unauthenticated access rejected (401)", r.status_code == 401, r.text)

    # 註冊一個一般成員（供後續成員/指派測試）
    member_username = "qa_member_" + uuid.uuid4().hex[:8]
    r = c.post(f"{api}/auth/register", json={
        "username": member_username, "display_name": "QA Member", "password": "MemberPass123"})
    reg_ok = check("register member", r.status_code in (200, 201), r.text)
    member_id = r.json().get("id") if reg_ok else None

    # ── 4. 專案 CRUD ─────────────────────────────────────────
    r = c.post(f"{api}/projects/", headers=H, json={"name": "QA 煙霧測試專案", "description": "e2e", "color": "#6366f1"})
    proj_ok = check("create project", r.status_code in (200, 201), r.text)
    if not proj_ok:
        summarize(); sys.exit(1)
    pid = r.json()["id"]

    r = c.get(f"{api}/projects/", headers=H)
    check("list projects", r.status_code == 200 and any(p["id"] == pid for p in r.json()), r.text)
    r = c.get(f"{api}/projects/{pid}", headers=H)
    check("get project detail", r.status_code == 200, r.text)
    r = c.patch(f"{api}/projects/{pid}", headers=H, json={"description": "updated"})
    check("update project", r.status_code == 200, r.text)
    r = c.get(f"{api}/projects/overview", headers=H)
    check("projects overview", r.status_code == 200, r.text)

    # ── 5. 成員管理 ──────────────────────────────────────────
    if member_id:
        r = c.post(f"{api}/projects/{pid}/members", headers=H, json={"user_id": member_id, "role": "member"})
        check("add project member", r.status_code in (200, 201), r.text)
    r = c.get(f"{api}/projects/{pid}/members", headers=H)
    check("list project members", r.status_code == 200, r.text)

    # ── 6. 任務 CRUD + 看板移動 ──────────────────────────────
    r = c.post(f"{api}/projects/{pid}/tasks/", headers=H, json={
        "title": "QA 任務 1", "description": "core", "priority": "high",
        "assignee_ids": [member_id] if member_id else []})
    task_ok = check("create task", r.status_code in (200, 201), r.text)
    if not task_ok:
        summarize(); sys.exit(1)
    tid = r.json()["id"]

    r = c.get(f"{api}/projects/{pid}/tasks/", headers=H)
    check("list tasks", r.status_code == 200 and any(t["id"] == tid for t in r.json()), r.text)
    r = c.get(f"{api}/projects/{pid}/tasks/{tid}", headers=H)
    check("get task detail", r.status_code == 200, r.text)
    r = c.patch(f"{api}/projects/{pid}/tasks/{tid}", headers=H, json={"title": "QA 任務 1（改）"})
    check("update task", r.status_code == 200, r.text)
    r = c.patch(f"{api}/projects/{pid}/tasks/{tid}/move", headers=H, json={"status": "in_progress", "position": 0})
    check("kanban move task", r.status_code == 200, r.text)

    # 第二個任務（供依賴測試）
    r = c.post(f"{api}/projects/{pid}/tasks/", headers=H, json={"title": "QA 任務 2"})
    tid2 = r.json().get("id") if r.status_code in (200, 201) else None

    # ── 7. 子任務 ────────────────────────────────────────────
    r = c.post(f"{api}/projects/{pid}/tasks/{tid}/subtasks/", headers=H, json={"title": "子任務 A"})
    sub_ok = check("create subtask", r.status_code in (200, 201), r.text)
    if sub_ok:
        sid = r.json()["id"]
        r = c.patch(f"{api}/projects/{pid}/tasks/{tid}/subtasks/{sid}", headers=H, json={"is_done": True})
        check("toggle subtask done", r.status_code in (200, 204), r.text)
    r = c.get(f"{api}/projects/{pid}/tasks/{tid}/subtasks/", headers=H)
    check("list subtasks", r.status_code == 200, r.text)

    # ── 8. 評論 + 反應 ───────────────────────────────────────
    r = c.post(f"{api}/projects/{pid}/tasks/{tid}/comments", headers=H, json={"content": "第一則評論 @qa"})
    cmt_ok = check("add comment", r.status_code in (200, 201), r.text)
    cmt_id = r.json().get("id") if cmt_ok else None
    if cmt_id:
        r = c.post(f"{api}/projects/{pid}/tasks/{tid}/comments/{cmt_id}/reactions/toggle",
                   headers=H, json={"emoji": "👍"})
        check("toggle comment reaction", r.status_code in (200, 201, 204), r.text)

    # ── 9. 依賴關係 ──────────────────────────────────────────
    if tid2:
        r = c.post(f"{api}/projects/{pid}/tasks/{tid}/dependencies/", headers=H, json={"to_task_id": tid2})
        check("create task dependency", r.status_code in (200, 201), r.text)
        r = c.get(f"{api}/projects/{pid}/tasks/{tid}/dependencies/", headers=H)
        check("list dependencies", r.status_code == 200, r.text)

    # ── 10. 時間追蹤 ─────────────────────────────────────────
    r = c.post(f"{api}/projects/{pid}/tasks/{tid}/time-logs/manual", headers=H,
               json={"minutes": 30, "note": "qa manual log"})
    check("manual time log", r.status_code in (200, 201), r.text)
    r = c.get(f"{api}/projects/{pid}/tasks/{tid}/time-logs/", headers=H)
    check("list time logs", r.status_code == 200, r.text)

    # ── 11. 每日任務 ─────────────────────────────────────────
    today = datetime.date.today().isoformat()
    r = c.post(f"{api}/daily-tasks/", headers=H, json={"title": "今日例行", "date": today})
    dt_ok = check("create daily task", r.status_code in (200, 201), r.text)
    r = c.get(f"{api}/daily-tasks/", headers=H, params={"date": today})
    check("list daily tasks", r.status_code == 200, r.text)

    # ── 12. 通知 ─────────────────────────────────────────────
    r = c.get(f"{api}/notifications/", headers=H)
    check("list notifications", r.status_code == 200, r.text)
    r = c.patch(f"{api}/notifications/read-all", headers=H)
    check("mark all notifications read", r.status_code in (200, 204), r.text)

    # ── 13. 儀表板 / 搜尋 / 日曆 / 工作量 ────────────────────
    r = c.get(f"{api}/dashboard/summary", headers=H)
    check("dashboard summary", r.status_code == 200, r.text)
    r = c.get(f"{api}/search/", headers=H, params={"q": "QA"})
    check("global search", r.status_code == 200, r.text)
    now = datetime.date.today()
    r = c.get(f"{api}/calendar/", headers=H, params={"year": now.year, "month": now.month})
    check("calendar", r.status_code == 200, r.text)
    r = c.get(f"{api}/workload", headers=H)
    check("workload", r.status_code == 200, r.text)
    r = c.get(f"{api}/insights", headers=H)
    check("insights", r.status_code == 200, r.text)
    r = c.get(f"{api}/weekly-report", headers=H)
    check("weekly report", r.status_code == 200, r.text)

    # ── 14. 範本 ─────────────────────────────────────────────
    r = c.get(f"{api}/project-templates/", headers=H)
    check("list project templates", r.status_code == 200, r.text)

    # ── 15. AI 建議 ──────────────────────────────────────────
    r = c.get(f"{api}/ai/priority-suggestions", headers=H)
    # AI 未設 key 時可能回退（仍應 200 + 結構），或 200 空
    check("AI priority suggestions", r.status_code == 200, r.text)

    # ── 16. 系統設定（admin）─────────────────────────────────
    r = c.get(f"{api}/system-settings/", headers=H)
    check("get system settings (admin)", r.status_code == 200, r.text)
    r = c.get(f"{api}/system-settings/tls-cert", headers=H)
    check("get tls cert info (admin)", r.status_code == 200, r.text)

    # ── 17. 公告 ─────────────────────────────────────────────
    r = c.get(f"{api}/announcements/", headers=H)
    check("list announcements", r.status_code == 200, r.text)

    # ── 18. 清理：刪除測試專案（驗證 DELETE）─────────────────
    r = c.delete(f"{api}/projects/{pid}", headers=H)
    check("delete project (cleanup)", r.status_code in (200, 204), r.text)

    summarize()


def summarize():
    total = len(PASS) + len(FAIL)
    rate = (len(PASS) / total * 100) if total else 0
    print("\n" + "=" * 50)
    print(f"通過 {len(PASS)} / {total}  通過率 {rate:.1f}%")
    if FAIL:
        print("失敗項目：")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 50)
    sys.exit(0 if not FAIL else 2)


if __name__ == "__main__":
    main()
