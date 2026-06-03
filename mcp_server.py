#!/usr/bin/env python3
"""
WorkFlow Universal MCP Server
支援多 AI 客戶端：Claude Code、Cursor、VS Code Copilot、Continue.dev、
ChatGPT Actions、Gemini 等任何支援 MCP 或 HTTP JSON-RPC 的客戶端。

傳輸模式：
  --transport stdio   本地 AI 直接 spawn（預設，Claude Code / Cursor / VS Code）
  --transport http    HTTP 服務模式（ChatGPT / Gemini / 遠端 AI，需 API Key）

快速啟動：
  # stdio 模式（本地 AI）
  python mcp_server.py

  # HTTP 模式（網頁 AI / 遠端）
  python mcp_server.py --transport http --port 8765

環境變數：
  WORKFLOW_URL      WorkFlow 後端位址（預設 http://localhost:8000）
  WORKFLOW_EMAIL    登入帳號（預設 admin@example.com）
  WORKFLOW_PASSWORD 登入密碼（預設 Admin1234!）
  MCP_API_KEY       HTTP 模式的 Bearer token 保護（建議設定）
  MCP_HOST          HTTP 模式監聽位址（預設 0.0.0.0）
  MCP_PORT          HTTP 模式監聽埠（預設 8765）
"""

import argparse
import json
import os
import sys
import time
from datetime import date as _date
from typing import Any

import httpx

# ── MCP SDK 引入（支援舊版 / 新版 API）────────────────────────
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    _MCP_OK = True
except ImportError:
    _MCP_OK = False

# ─────────────────────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────────────────────
WORKFLOW_URL = os.getenv("WORKFLOW_URL", "http://localhost:8000")
EMAIL        = os.getenv("WORKFLOW_EMAIL", "admin@example.com")
PASSWORD     = os.getenv("WORKFLOW_PASSWORD", "Admin1234!")
MCP_API_KEY  = os.getenv("MCP_API_KEY", "")   # HTTP 模式保護用
MCP_HOST     = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT     = int(os.getenv("MCP_PORT", "8765"))

# ─────────────────────────────────────────────────────────────
# WorkFlow API 客戶端（自動 token 管理）
# ─────────────────────────────────────────────────────────────
class WorkFlowClient:
    def __init__(self) -> None:
        self._access:  str   = ""
        self._refresh: str   = ""
        self._exp:     float = 0.0

    def _login(self) -> None:
        r = httpx.post(f"{WORKFLOW_URL}/api/v1/auth/login",
                       json={"email": EMAIL, "password": PASSWORD}, timeout=10)
        r.raise_for_status()
        d = r.json()
        self._access  = d["access_token"]
        self._refresh = d["refresh_token"]
        self._exp = time.time() + 55 * 60   # 55 分鐘後刷新

    def _token(self) -> str:
        if not self._access or time.time() > self._exp:
            self._login()
        return self._access

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}"}

    def get(self, path: str, params: dict | None = None) -> Any:
        r = httpx.get(f"{WORKFLOW_URL}{path}", headers=self._h(), params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: Any) -> Any:
        r = httpx.post(f"{WORKFLOW_URL}{path}", headers=self._h(), json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def patch(self, path: str, body: Any) -> Any:
        r = httpx.patch(f"{WORKFLOW_URL}{path}", headers=self._h(), json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str) -> dict:
        r = httpx.delete(f"{WORKFLOW_URL}{path}", headers=self._h(), timeout=15)
        r.raise_for_status()
        return {"ok": True}

wf = WorkFlowClient()

# ─────────────────────────────────────────────────────────────
# 工具定義（所有模式共用）
# ─────────────────────────────────────────────────────────────
TOOL_DEFS: list[dict] = [
    {
        "name": "get_dashboard",
        "description": "取得個人儀表板：待辦數、逾期數、本週完成數 KPI，以及需我處理的任務清單。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_projects",
        "description": "列出目前使用者有權限的所有專案（名稱、ID、成員數、顏色）。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_project",
        "description": "建立新專案。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name":        {"type": "string", "description": "專案名稱"},
                "description": {"type": "string"},
                "color":       {"type": "string", "description": "HEX 色碼，例如 #6366f1"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_tasks",
        "description": "列出指定專案的所有任務，含狀態、優先度、指派人、截止日。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "專案 ID"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "create_task",
        "description": "在指定專案建立新任務，可指定優先度、截止日、指派人。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id":   {"type": "string"},
                "title":        {"type": "string"},
                "description":  {"type": "string"},
                "priority":     {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "status":       {"type": "string", "enum": ["todo", "in_progress", "review", "done"]},
                "due_date":     {"type": "string", "description": "格式 yyyy-mm-dd"},
                "start_date":   {"type": "string", "description": "格式 yyyy-mm-dd"},
                "assignee_ids": {"type": "array", "items": {"type": "string"}, "description": "指派人 user ID 陣列"},
            },
            "required": ["project_id", "title"],
        },
    },
    {
        "name": "update_task",
        "description": "更新任務的狀態、優先度、進度百分比、截止日或標題。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id":    {"type": "string"},
                "title":      {"type": "string"},
                "status":     {"type": "string", "enum": ["todo", "in_progress", "review", "done"]},
                "priority":   {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "progress":   {"type": "integer", "minimum": 0, "maximum": 100},
                "due_date":   {"type": "string", "description": "格式 yyyy-mm-dd"},
                "description":{"type": "string"},
            },
            "required": ["project_id", "task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "刪除指定任務（不可逆）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id":    {"type": "string"},
            },
            "required": ["project_id", "task_id"],
        },
    },
    {
        "name": "move_task",
        "description": "移動任務到不同狀態欄（Kanban 移動）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id":    {"type": "string"},
                "status":     {"type": "string", "enum": ["todo", "in_progress", "review", "done"]},
                "position":   {"type": "integer", "description": "欄內位置（0 = 最上方）", "default": 0},
            },
            "required": ["project_id", "task_id", "status"],
        },
    },
    {
        "name": "add_comment",
        "description": "在任務新增評論，支援 @mention 觸發通知（例：@John）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id":    {"type": "string"},
                "content":    {"type": "string", "description": "評論內容，可用 @display_name 提及成員"},
            },
            "required": ["project_id", "task_id", "content"],
        },
    },
    {
        "name": "search",
        "description": "全站搜尋任務、專案或日常作業，回傳匹配項目清單。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q":    {"type": "string", "description": "搜尋關鍵字"},
                "type": {"type": "string", "enum": ["all", "task", "project", "daily"], "default": "all"},
            },
            "required": ["q"],
        },
    },
    {
        "name": "list_daily_tasks",
        "description": "列出日常作業，預設今日，可依日期或標籤篩選。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date":  {"type": "string", "description": "格式 yyyy-mm-dd，留空為今日"},
                "label": {"type": "string", "description": "標籤篩選"},
            },
            "required": [],
        },
    },
    {
        "name": "create_daily_task",
        "description": "建立日常作業，可指定日期、標籤、預估工作分鐘數。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title":        {"type": "string"},
                "date":         {"type": "string", "description": "格式 yyyy-mm-dd，預設今日"},
                "description":  {"type": "string"},
                "status":       {"type": "string", "enum": ["pending", "in_progress", "done", "cancelled"]},
                "labels":       {"type": "array", "items": {"type": "string"}},
                "work_minutes": {"type": "integer", "minimum": 0},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_daily_task",
        "description": "更新日常作業的標題、狀態、進度、日期或標籤。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id":      {"type": "string"},
                "title":        {"type": "string"},
                "status":       {"type": "string", "enum": ["pending", "in_progress", "done", "cancelled"]},
                "progress":     {"type": "integer", "minimum": 0, "maximum": 100},
                "date":         {"type": "string", "description": "格式 yyyy-mm-dd"},
                "description":  {"type": "string"},
                "labels":       {"type": "array", "items": {"type": "string"}},
                "work_minutes": {"type": "integer", "minimum": 0},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_daily_task",
        "description": "刪除日常作業（不可逆）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "list_members",
        "description": "列出專案成員（名稱、ID、角色）。可用回傳的 user ID 指派任務。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "list_notifications",
        "description": "取得目前使用者的通知清單與未讀數。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_time_report",
        "description": "取得工時報表，可依專案或成員篩選。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "限定專案（選填）"},
                "user_id":    {"type": "string", "description": "限定成員（選填，預設自己）"},
            },
            "required": [],
        },
    },
    {
        "name": "list_milestones",
        "description": "列出專案里程碑與關聯任務數。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
]

# ─────────────────────────────────────────────────────────────
# 工具執行邏輯（所有模式共用）
# ─────────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> Any:
    """執行工具並回傳結果（dict / list）。失敗時 raise。"""
    a = dict(args)   # 不修改原始參數
    match name:
        case "get_dashboard":
            return wf.get("/api/v1/dashboard/summary")

        case "list_projects":
            return wf.get("/api/v1/projects/")

        case "create_project":
            return wf.post("/api/v1/projects/", a)

        case "list_tasks":
            return wf.get(f"/api/v1/projects/{a['project_id']}/tasks/")

        case "create_task":
            pid = a.pop("project_id")
            return wf.post(f"/api/v1/projects/{pid}/tasks/", a)

        case "update_task":
            pid = a.pop("project_id")
            tid = a.pop("task_id")
            return wf.patch(f"/api/v1/projects/{pid}/tasks/{tid}", a)

        case "delete_task":
            pid = a.pop("project_id")
            tid = a.pop("task_id")
            return wf.delete(f"/api/v1/projects/{pid}/tasks/{tid}")

        case "move_task":
            pid = a.pop("project_id")
            tid = a.pop("task_id")
            status   = a.get("status")
            position = a.get("position", 0)
            return wf.patch(f"/api/v1/projects/{pid}/tasks/{tid}/move",
                            {"status": status, "position": position})

        case "add_comment":
            pid = a.pop("project_id")
            tid = a.pop("task_id")
            return wf.post(f"/api/v1/projects/{pid}/tasks/{tid}/comments",
                           {"content": a["content"]})

        case "search":
            return wf.get("/api/v1/search/",
                          {"q": a["q"], "type": a.get("type", "all")})

        case "list_daily_tasks":
            params: dict = {}
            if a.get("date"):  params["date"]  = a["date"]
            if a.get("label"): params["label"] = a["label"]
            return wf.get("/api/v1/daily-tasks/", params or None)

        case "create_daily_task":
            if "date" not in a:
                a["date"] = _date.today().isoformat()
            return wf.post("/api/v1/daily-tasks/", a)

        case "update_daily_task":
            tid = a.pop("task_id")
            return wf.patch(f"/api/v1/daily-tasks/{tid}", a)

        case "delete_daily_task":
            tid = a.pop("task_id")
            return wf.delete(f"/api/v1/daily-tasks/{tid}")

        case "list_members":
            raw = wf.get(f"/api/v1/projects/{a['project_id']}/members/")
            # 展平成 AI 容易讀的格式
            return [
                {"id": m["user"]["id"], "display_name": m["user"]["display_name"],
                 "email": m["user"]["email"], "role": m["role"]}
                for m in raw
            ]

        case "list_notifications":
            return wf.get("/api/v1/notifications/")

        case "get_time_report":
            params = {}
            if a.get("project_id"): params["project_id"] = a["project_id"]
            if a.get("user_id"):    params["user_id"]    = a["user_id"]
            return wf.get("/api/v1/time-logs/report", params or None)

        case "list_milestones":
            return wf.get(f"/api/v1/projects/{a['project_id']}/milestones/")

        case _:
            raise ValueError(f"未知工具：{name}")


def _tool_result_text(name: str, args: dict) -> str:
    """執行工具，將結果轉為字串（供 stdio / HTTP 兩種模式共用）。"""
    try:
        result = execute_tool(name, args)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"API {e.response.status_code}", "detail": e.response.text})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────
# 模式 A：stdio（本地 AI 客戶端）
# ─────────────────────────────────────────────────────────────
def run_stdio() -> None:
    if not _MCP_OK:
        print("錯誤：stdio 模式需要 MCP SDK，請執行 pip install mcp", file=sys.stderr)
        sys.exit(1)

    import asyncio

    server = Server("workflow")
    tools  = [Tool(name=t["name"], description=t["description"],
                   inputSchema=t["inputSchema"]) for t in TOOL_DEFS]

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
        text = _tool_result_text(name, arguments)
        return [TextContent(type="text", text=text)]

    asyncio.run(stdio_server(server))


# ─────────────────────────────────────────────────────────────
# 模式 B：HTTP（網頁 AI / 遠端客戶端，JSON-RPC 2.0 over HTTP）
# ─────────────────────────────────────────────────────────────
def run_http(host: str, port: int) -> None:
    try:
        from fastapi import FastAPI, Request, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn
    except ImportError:
        print("錯誤：HTTP 模式需要 FastAPI + uvicorn，請執行：\n"
              "  pip install fastapi uvicorn[standard]", file=sys.stderr)
        sys.exit(1)

    http_app = FastAPI(
        title="WorkFlow MCP Server",
        description="MCP-compatible HTTP endpoint for WorkFlow API",
        version="1.0.0",
    )

    def _check_auth(request: Request) -> None:
        if not MCP_API_KEY:
            return   # 未設定 API Key = 不驗證（僅限本機使用）
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != MCP_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid MCP_API_KEY")

    # MCP Streamable HTTP：POST /mcp
    @http_app.post("/mcp")
    async def mcp_endpoint(request: Request) -> JSONResponse:
        _check_auth(request)
        body = await request.json()
        rpc_id     = body.get("id")
        method     = body.get("method", "")
        params     = body.get("params", {})

        def ok(result: Any) -> JSONResponse:
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})

        def err(code: int, message: str) -> JSONResponse:
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                                 "error": {"code": code, "message": message}})

        match method:
            case "initialize":
                return ok({
                    "protocolVersion": "2025-03-26",
                    "serverInfo":      {"name": "workflow", "version": "1.0.0"},
                    "capabilities":    {"tools": {"listChanged": False}},
                })
            case "tools/list":
                return ok({"tools": TOOL_DEFS})
            case "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                text = _tool_result_text(tool_name, arguments)
                return ok({"content": [{"type": "text", "text": text}]})
            case "ping":
                return ok({})
            case _:
                return err(-32601, f"Method not found: {method}")

    # 健康檢查
    @http_app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "server": "workflow-mcp", "workflow_url": WORKFLOW_URL}

    # OpenAPI-style 工具清單（ChatGPT Plugin / Gemini 等使用 REST 的 AI）
    @http_app.get("/tools")
    async def list_tools_rest(request: Request) -> JSONResponse:
        _check_auth(request)
        return JSONResponse({"tools": TOOL_DEFS})

    @http_app.post("/tools/{tool_name}")
    async def call_tool_rest(tool_name: str, request: Request) -> JSONResponse:
        _check_auth(request)
        body = await request.json()
        text = _tool_result_text(tool_name, body)
        try:
            result = json.loads(text)
        except Exception:
            result = {"text": text}
        return JSONResponse(result)

    print(f"WorkFlow MCP Server (HTTP) 啟動於 http://{host}:{port}")
    print(f"  MCP endpoint : POST http://{host}:{port}/mcp")
    print(f"  REST tools   : GET  http://{host}:{port}/tools")
    print(f"  Health check : GET  http://{host}:{port}/health")
    if MCP_API_KEY:
        print(f"  API Key 保護 : 已啟用（Bearer {MCP_API_KEY[:8]}...）")
    else:
        print("  ⚠️  MCP_API_KEY 未設定，任何人都可呼叫（建議僅本機使用）")

    uvicorn.run(http_app, host=host, port=port)


# ─────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="WorkFlow Universal MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                        help="傳輸模式：stdio（本地 AI）或 http（網頁 AI / 遠端）")
    parser.add_argument("--host", default=MCP_HOST, help=f"HTTP 模式監聽位址（預設 {MCP_HOST}）")
    parser.add_argument("--port", type=int, default=MCP_PORT, help=f"HTTP 模式監聽埠（預設 {MCP_PORT}）")
    args = parser.parse_args()

    if args.transport == "stdio":
        run_stdio()
    else:
        run_http(args.host, args.port)


if __name__ == "__main__":
    main()
