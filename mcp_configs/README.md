# WorkFlow MCP 設定說明

## 安裝依賴

```bash
# stdio 模式（本地 AI：Claude Code / Cursor / VS Code）
pip install httpx mcp

# HTTP 模式（網頁 AI：ChatGPT / Gemini）另需：
pip install fastapi "uvicorn[standard]"
```

## 兩種傳輸模式

| 模式 | 適用客戶端 | 啟動方式 |
|------|-----------|---------|
| `stdio` | Claude Code、Cursor、VS Code、Continue.dev、Windsurf | AI 自動 spawn 進程 |
| `http`  | ChatGPT Actions、Gemini、任何 HTTP 客戶端 | 需手動先啟動服務 |

---

## 各客戶端設定方式

### Claude Code（stdio）
```bash
claude mcp add workflow -- python c:/GIT/WF/workflow/mcp_server.py
```
或手動編輯 `%APPDATA%\Claude\claude_desktop_config.json`：
見 `claude_desktop.json`

### Cursor（stdio）
見 `.cursor/mcp.json`

### VS Code GitHub Copilot（stdio）
見 `.vscode/mcp.json`

### Continue.dev（stdio）
見 `continue_config.json`

### ChatGPT / Gemini（HTTP）
先啟動 HTTP server：
```bash
set MCP_API_KEY=my-secret-key
python c:/GIT/WF/workflow/mcp_server.py --transport http --port 8765
```
再設定 OpenAPI URL：`http://localhost:8765/tools`

---

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `WORKFLOW_URL` | WorkFlow API 位址 | `http://localhost:8000` |
| `WORKFLOW_EMAIL` | 登入帳號 | `admin@example.com` |
| `WORKFLOW_PASSWORD` | 登入密碼 | `Admin1234!` |
| `MCP_API_KEY` | HTTP 模式 Bearer token（建議設定） | 空（不驗證） |
| `MCP_HOST` | HTTP 監聽位址 | `0.0.0.0` |
| `MCP_PORT` | HTTP 監聽埠 | `8765` |
