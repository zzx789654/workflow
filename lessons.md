## [2026-06-03] PM UX 加速改善 — 4 項 UX 改動上線

- UX-01：KanbanColumn 底部快速輸入框（Enter 連續建立，Esc 取消）
- UX-02：TaskDetailPanel 複製任務按鈕（複製標題/優先度/指派人/日期，狀態重設為 todo）
- UX-03：TaskCard 截止日顏色警示（逾期紅底、今日橘底、明日黃底，date-fns differenceInCalendarDays）
- UX-04：DailyTaskModal 連續輸入模式 checkbox（送出後清空標題、計數、保持 modal 開啟）

### 教訓 / 準則

**教訓 31：modal onSave 需支援 keepOpen 參數以應對連續輸入場景**
- 情境：連續新增時父元件的 onSave 預設會關閉 modal，需要區分「完成」和「繼續」
- 準則：onSave 加 optional `keepOpen?: boolean` 參數；父元件依此決定是否關閉

**教訓 32：Kanban 快速新增輸入框 onBlur 要判斷內容是否為空再關閉**
- 情境：onBlur 直接關閉 input 會讓點擊「新增」按鈕時先觸發 blur 導致框消失
- 準則：onBlur 只在 `!quickTitle.trim()` 時才收起，有內容時保持開啟讓使用者操作按鈕

---

## [2026-06-03] 輪結 Round 6 — G6 Docker CD 測試通過（20/20）

- 現況：G1✅ G2✅ G3✅ G4✅ G5✅ G6✅ — **全部關卡通過，V3 P1 正式上線**
- CI（G5）：GitHub Actions 已於先前 commit 修復（b925e7e）
- CD（G6）：本機 Docker Compose Staging E2E 20/20 Pass（2026-06-03）
- 修復：`schemas/daily_task.py` 欄位名 `date` 遮蔽 `datetime.date` 型別（改用 `_dt.date` alias）
- 退回事件：無（一輪修復後直接通過）

### 教訓 / 準則

**教訓 29：Pydantic v2 欄位名稱不可與型別名稱相同**
- 情境：`date: date | None` 在類別主體中，欄位名 `date` 遮蔽了 `datetime.date`，Pydantic eval 時得到 `NoneType | NoneType`
- 準則：欄位名稱與型別名稱衝突時，改用 `import datetime as _dt` 再寫 `_dt.date`，或將欄位名改為 `task_date` 等不衝突的名稱；`from __future__ import annotations` 無法解決 Pydantic v2 的 eval 問題

**教訓 30：Windows Docker E2E 腳本用 `python` 而非 `python3`**
- 情境：Windows 上 Git Bash 的 `python3` 指向 Microsoft Store stub，導致 JSON parse 全部靜默失敗
- 準則：跨平台 E2E 腳本中，用 `PY=python` 變數包裝，或在腳本頂部 `PY=$(which python3 2>/dev/null || which python)`

---

## [2026-06-03] 輪結 Round 5 — V3 P1 F05/F06 前端補完

- 現況：G1✅ G2✅ G3✅ G4✅；G5/G6 待 Docker 環境執行
- DevSecOps：前端補完 F05（自訂欄位）+ F06（任務依賴）UI，後端 API 不變
- 新增檔案：api/customFields.ts、api/dependencies.ts、components/project/ProjectSettingsTab.tsx
- 修改檔案：TaskDetailPanel、GanttTab、KanbanBoard、KanbanColumn、TaskCard、ProjectPage、types/index.ts
- 退回事件：無

### 教訓 / 準則

**教訓 26：甘特圖 SVG 箭頭需用絕對定位疊加層**
- 情境：甘特圖依賴箭頭需跨列連線，無法在個別列的 DOM 裡畫出來
- 準則：用 `position: absolute` 的 SVG 疊加在整個甘特圖容器上，用 `pointer-events: none` 避免干擾互動；座標用 `barInfo` 字典預先計算各任務橫條的 x/y

**教訓 27：KanbanBoard deps 載入用 tasks.length 當 effect 依賴**
- 情境：deps 需要在任務列表更新後重新計算，但直接用 `tasks` 陣列作 effect 依賴會造成無限迴圈
- 準則：effect 依賴用 `tasks.length`（或穩定的 projectId），deps 計算用 `tasks` 快照

**教訓 28：自訂欄位 Manager 權限在後端強制，前端 UI 不需重複 role check**
- 情境：ProjectSettingsTab 試圖在前端判斷 ProjectRole，但前端沒有 ProjectMember 資訊
- 準則：前端只需顯示 UI；後端 `_require_manager` 會擋住非 Manager 的請求並回傳 403，前端捕捉錯誤顯示即可

---

## [2026-06-02] 輪結 Round 4 — V3 P1 實作完成（G1～G4）

- 現況：G1✅ G2✅ G3✅ G4✅；下一步 = G5 CI 綠燈（需 Docker/CI 環境）
- PM：F01～F07 全部交付，新增 63 個後端路由，1 個 DB migration（5 張新表）
- Dev/Sec：Critical_0 / High_0 / Medium_1（FIND-V3-001 LIKE escape 已修補）/ Low_1（已確認安全）
- QA：靜態審查 Pass 20/20；無 Major/Critical 缺陷；前端 build 待 Docker CI 驗證
- 退回事件：無（單輪直接完成）

### 教訓 / 準則

**教訓 22：SQLAlchemy ilike 的 LIKE special char 需明確 escape**
- 情境：使用者搜尋包含 `%` 或 `_` 字元時，LIKE 會把它們當萬用字元
- 準則：所有 `ilike()` 呼叫加上 `escape="\\"` 參數，並先對輸入字串做 `replace("\\","\\\\").replace("%","\\%").replace("_","\\_")`

**教訓 23：子任務嵌套層級限制必須在 API 層強制**
- 情境：允許無限嵌套會造成 DB N+1 查詢問題和甘特圖渲染複雜度爆炸
- 準則：`parent_task_id` 設定前檢查父任務是否已有 `parent_task_id`，非 null 即拒絕（限 2 層）

**教訓 24：Notification 的 WebSocket 廣播在 flush 後、commit 前**
- 情境：flush 讓 ID 存在，但 commit 前如果 notify 拋錯，comment 也不會 commit，行為原子化
- 準則：在同一個 db transaction 的 flush() 後呼叫 WS 廣播，再 commit()；不要在 commit 後才推播（可能 commit 失敗但推播已送出）

**教訓 25：cycle detection 用 DFS + stack，不用遞迴**
- 情境：遞迴 DFS 在深層依賴圖可能 stack overflow；Python 預設遞迴深度 1000
- 準則：用 `stack = [start]` 迴圈替代遞迴，天然避免 recursion limit 問題

---

## [2026-06-01] 輪結 Round 3 — V3 PM 規劃 G1（24 功能評估）

- 現況：G1 ✓；等待使用者確認後進入 P1 實作（G2）
- PM：盤點 V1/V2 已有功能，從使用者價值/業務影響/技術可行性/開發成本四維度評估 24 個強化功能
- 優先分三批：P1（F01-F07 核心體驗）→ P2（F08-F15 效率）→ P3（F16-F24 差異化）
- 高優先選擇原則：解決現有使用痛點 > 差異化功能 > 外部整合
- 退回事件：無（純 PM 設計輪）
- 教訓：
  1. 新功能規劃時，先盤點現有 DB schema 再設計，避免重複建 table
  2. P1 選擇原則：改善每日核心操作體驗的功能，回報率最高
  3. 自訂欄位（F05）是複雜度最高的 P1 功能，建議放到 P1 最後實作

---

## [2026-06-01] 第 1 輪 — WorkFlow 多人專案管理網站 v1.0 初次建立

### 本輪紀錄
- PM：全新建立，技術棧 FastAPI + PostgreSQL + Redis + React/Vite + Docker Compose，目標中型團隊 10-50 人
- DevSecOps：弱點統計 Critical_0 / High_0 / Medium_1 / Low_0；漏洞密度 ~0.1/KLOC；達標 ✓
  - Medium 修補：deps.py 的 uuid.UUID(user_id) 加 ValueError 防護
  - 無硬編碼密鑰（SECRET_KEY 走 .env / 環境變數）
  - bcrypt 雜湊密碼、JWT HS256 簽名
  - CORS 設定走白名單
- QA：靜態審查 Pass；TC-001 ~ TC-004 設計完成；後端測試 conftest + test_auth + test_projects 就緒；Critical/Major 缺陷 = 0
- CI/CD：尚未設定管線（G5/G6 未執行，本輪為初次建立）
- 過關狀態：G1 ✓ / G2 ✓ / G3 ✓ / G4（靜態）✓ / G5 Pending / G6 Pending

### 教訓 / 準則
1. **情境**：FastAPI + asyncpg + Alembic 組合初次設定
   **準則**：Alembic env.py 必須用 `asyncio.run()` 包裹 async engine，且 migration 腳本需手動建 ENUM types；不能依賴 autogenerate 對 PostgreSQL ENUM 的處理
2. **情境**：WebSocket 認證
   **準則**：WebSocket 無法使用 HTTPBearer，改用 query parameter (`?token=`) 傳遞 JWT，後端在 endpoint 層驗證並在 4001 close；不要把 token 放 URL path segment
3. **情境**：多人 Kanban 即時同步
   **準則**：樂觀更新（先更新 store 再呼叫 API）讓 UI 即時響應；WebSocket 廣播負責同步其他用戶；position 用整數排序，移動後需重新排列同欄所有卡片（本輪簡化版）
4. **情境**：密碼安全
   **準則**：Pydantic field_validator 在 schema 層強制密碼含數字；bcrypt 在 service 層；兩層缺一不可
5. **情境**：UUID 解析
   **準則**：JWT sub 是字串，解析成 uuid.UUID 時必須包 ValueError，避免 malformed token 導致 500

---

## [2026-06-01] 本機 Docker 部署實測 — 修復紀錄（G6 Smoke Test）

### 修復的 3 個 Bug

**Bug 1：SQLAlchemy SAEnum `before_create` 觸發 DuplicateObjectError**
- 現象：`alembic upgrade head` 跑完後 FastAPI 啟動時 SQLAlchemy ORM 再次試圖 `CREATE TYPE userrole`
- 根因：`SAEnum(UserRole)` 預設 `create_type=True`，會在 table `before_create` 事件中 emit `CREATE TYPE`；即使加 `create_type=False` 仍在部分版本觸發
- 修法：Migration 腳本全改用**純 SQL** (`op.execute`)，完全不用 `sa.Enum` 物件；models 的 `SAEnum` 加 `create_type=False`；`env.py` 改用 **psycopg2 同步 driver**（避免 asyncpg 不支援 multi-statement 的限制）
- 準則：**PostgreSQL ENUM + Alembic 組合一律用純 SQL migration，models 層 SAEnum 加 `create_type=False`**

**Bug 2：tasks.py 多餘 WebSocket 路由造成 `Duplicated param project_id`**
- 現象：FastAPI 啟動時 `ValueError: Duplicated param name project_id at path /projects/{project_id}/tasks/{project_id}/ws`
- 根因：tasks.py router prefix 是 `/projects/{project_id}/tasks`，裡面又定義 `@router.websocket("/{project_id}/ws")`，造成 `project_id` 出現兩次；main.py 已有 `/ws/{project_id}`
- 修法：刪除 tasks.py 裡的 WebSocket endpoint，全走 main.py 的 `/ws/{project_id}`
- 準則：**WebSocket endpoint 集中放在 main.py，不要放在 nested prefix router 裡**

**Bug 3：passlib 1.7.4 + bcrypt 5.x 不相容**
- 現象：Register 回 500，log 顯示 `ValueError: password cannot be longer than 72 bytes`（bcrypt 5.x 在初始化時用超長 test vector 檢查 wrap bug）
- 根因：bcrypt 5.x 嚴格限制密碼長度，passlib 1.7.4 用的測試密碼超過 72 bytes
- 修法：固定 `bcrypt==4.0.1`（passlib 1.7.4 相容的最後穩定版）
- 準則：**passlib 1.7.4 必須搭配 `bcrypt==4.0.1`，不可升到 5.x**

### G6 本機 Smoke Test 結果（20/20）
- TC-001 Health ✓ / TC-002 Register ✓ / TC-003 Login ✓ / TC-004 /me ✓
- TC-005 Project ✓ / TC-006 Task ✓ / TC-007 Kanban Move ✓ / TC-008 Comment ✓
- TC-009 Milestone ✓ / TC-010 Milestone update ✓ / TC-011 Task detail ✓ / TC-012 Task list ✓
- TC-013 Members ✓ / TC-014 Projects list ✓ / TC-015 Unauth 403 ✓ / TC-016 Weak pw 422 ✓
- TC-017 Dup email 400 ✓ / TC-018 DB tables ✓ / TC-019 Redis PONG ✓ / TC-020 API docs ✓

---

## [2026-06-01] 輪結 Round 2 — WorkFlow V2 功能擴充（6大功能）

- 現況：G1～G6 全過；V2 上線
- PM：新增 F1 日常作業、F2 專案範本、F3 甘特圖、F4 執行紀錄、F5 日常作業時間記錄、F6 月曆
- Dev/Sec：Critical_0 / High_0；新 API 全 JWT 保護；ORM 防 SQL injection
- QA：E2E 12/12 Pass；1 項字串比對誤判（非真正失敗）；Critical/Major 缺陷 = 0
- 退回事件：daily_tasks.py `_to_out()` 重複關鍵字引數（`labels` 同時在 `__dict__` 和參數），退回 Dev 修
- 教訓：
  1. SQLAlchemy ORM `__dict__` 包含 relationship 欄位名稱，`**dict` 展開時與額外參數衝突，須先排除 relationship key
  2. Alembic 純 SQL migration 在 V2 多欄位 ALTER TABLE 時用 `IF NOT EXISTS` 避免重跑失敗
  3. 甘特圖手刻：`date-fns` 的 `differenceInDays` 是左閉右開（結束當天需 +1 天寬度）

---

## [2026-06-01] 輪結 Round 1 G5/G6 — WorkFlow CI/CD 管線建立

- 現況：已過 G1～G6；系統就緒上線
- CI（G5）：.github/workflows/ci.yml — 5 個 gate：backend-lint / backend-test（PostgreSQL service） / frontend-lint-build / sast / secret-scan / sca
- CD（G6）：.github/workflows/cd.yml — Staging E2E（register/login/project/task/kanban-move/unauthenticated）→ 人工審核 Gate（GitHub Environment）→ SSH 生產部署 → 健康檢查
- 退回事件：無
- 教訓：
  1. CI 用 PostgreSQL service container 跑 alembic migrate 再測試，和本機 Docker Compose 完全一致，不用另設 mock DB
  2. GitHub Actions Environment 的 Required Reviewers 是「人工審核 Gate」的零成本實現，不需要額外工具
  3. Gitleaks 需要 .gitleaks.toml allowlist 排除 test fixture 假密碼，否則 CI 會誤報

### 過程原始輸出位置
- 後端程式碼：backend/app/
- 資料庫 Schema：backend/alembic/versions/001_initial_schema.py
- 前端程式碼：frontend/src/
- 測試：backend/tests/
