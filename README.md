# WorkFlow

讓組織內部團隊，以「任務」為核心，簡單清楚地協同推進每天的工作。
打開就知道我今天要做什麼、誰在等我、哪件事卡住了。

技術棧：FastAPI + PostgreSQL + Redis + React/Vite + TailwindCSS。

---

## 目錄

- [選擇部署方式](#選擇部署方式)
- [方式 A — Docker 部署](#方式-a--docker-部署)
- [方式 B — Ubuntu 裸機部署（非 Docker）](#方式-b--ubuntu-裸機部署非-docker)
- [方式 C — Windows Docker 部署](#方式-c--windows-docker-部署)
- [首次登入（兩種方式通用）](#首次登入兩種方式通用)
- [認證方式（本地 / LDAP / RADIUS）](#認證方式本地--ldap--radius)
- [更換 TLS 憑證（兩種方式通用）](#更換-tls-憑證兩種方式通用)
- [本機開發](#本機開發)
- [測試](#測試)
- [套件版本](#套件版本)

---

## 選擇部署方式

三種方式擇一即可。都會自動產生強密鑰、建立管理者帳號，完成時印出 admin 登入密碼；
都是 nginx 唯一對外（80/443），DB/Redis/backend 不對外暴露。方式 A 與方式 C 用的是
**同一份** `docker-compose.prod.yml`，只是安裝腳本依作業系統不同（bash / PowerShell）。

| | 方式 A：Linux Docker | 方式 B：Ubuntu 裸機 | 方式 C：Windows Docker |
|---|---|---|---|
| 安裝腳本 | `install.sh` | `install-native.sh` | `install.ps1` |
| 作業系統 | Linux（Ubuntu 24.04） | Ubuntu 24.04 | Windows 10/11、Server 2022 |
| 相依 | Docker Engine | apt 系統套件 + Python venv | 只需 Docker Desktop |
| 服務管理 | Docker Compose 容器 | systemd 原生服務 | Docker Compose 容器 |
| 隔離 | 容器隔離 | systemd 強化 + 服務隔離 | 容器隔離（WSL2 後端） |
| 升級 | 重 build image | `git pull` + 重跑腳本 | 重 build image |
| 適用 | 多環境一致、易遷移 | 單機長期運行、較省資源 | 開發機 / Windows 環境快速試跑 |

> 共同需求：對外開放 80/443、主機可連外、建議 2 vCPU / 4 GB RAM 以上
> （首次會在主機上 build，較吃資源）。
> 方式 A／B 需 Ubuntu 24.04、能 `sudo` 的帳號；方式 C 需已安裝並啟動的 Docker Desktop。

---

## 方式 A — Docker 部署

整套服務（前端、後端、PostgreSQL、Redis、nginx）由 Docker Compose 管理。

### A-1. 部署步驟

```bash
# 1) 取得程式碼
git clone https://github.com/zzx789654/workflow.git workflow
cd workflow

# 2) 一鍵部署（需 sudo）
sudo ./install.sh

# 可選：指定網域（憑證 CN 與 CORS 會用它）
sudo DOMAIN=workflow.example.com ./install.sh
```

腳本依序：

1. 檢查系統、安裝 Docker Engine + compose plugin（已裝則跳過）。
2. 建立 `.env`：自動產生 `SECRET_KEY` / `SETTINGS_ENCRYPT_KEY`，並設定資料庫密碼與
   管理員密碼（留空自動產生強密碼）。
3. 產生自簽 TLS 憑證並注入憑證 volume。
4. `docker compose -f docker-compose.prod.yml up -d --build` 建置並啟動。
5. 等待後端健康檢查，印出存取資訊。

完成後瀏覽 `https://<主機>/`。

### A-2. 架構

```
瀏覽器 ──443/HTTPS──> nginx ──┬─ /            靜態前端（SPA）
                              ├─ /api/  ────> backend:8000
                              └─ /ws    ────> backend:8000（WebSocket）
                                   backend ──> db:5432（內網）
                                            └─ redis:6379（內網）
   reloader sidecar：監看憑證變更 → 熱重載 nginx
```

只有 nginx 對外；DB/Redis/backend 都在 compose 內網。憑證放共享 volume，前端上傳後
由獨立 reloader 觸發 nginx 重載（backend 不接觸 Docker，維持最小權限）。

### A-3. 日常維運

所有指令在專案根目錄執行（`<專案>` 為資料夾名，compose project 名同它）：

```bash
# 服務狀態 / 日誌
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f          # 全部
docker compose -f docker-compose.prod.yml logs -f backend  # 只看後端

# 停止 / 啟動
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 更新版本（拉新程式碼後重建）
git pull
docker compose -f docker-compose.prod.yml up -d --build

# 資料庫備份 / 還原（容器名 <專案>-db-1，可用 docker ps 確認）
docker exec <專案>-db-1 pg_dump -U workflow workflow_db > backup_$(date +%F).sql
cat backup_2026-06-10.sql | docker exec -i <專案>-db-1 psql -U workflow -d workflow_db
```

附件存於 `<專案>_uploads_data` volume；憑證存於 `<專案>_certs_data` volume；
資料庫存於 named volume，不隨容器刪除而消失（仍需定期備份）。

### A-4. Docker 疑難排解

| 症狀 | 處理 |
|------|------|
| `https://...` 連不上 | `ps` 看服務是否 Up；`logs nginx` 看憑證是否存在 |
| 後端一直不健康 | `logs backend`；常見為 `.env` 的 DB 密碼與 db 服務不一致，或 migration 失敗 |
| 改了 `.env` 沒生效 | 需 `down` 再 `up -d`（重建容器才會讀新環境變數） |
| 想換網域 | 改 `.env` 的 `CORS_ORIGINS`，重新上傳對應網域憑證，`up -d` |

---

## 方式 C — Windows Docker 部署

在 Windows 上用 **Docker Desktop** 跑同一套 production 容器（前端、後端、PostgreSQL、
Redis、nginx），由 PowerShell 腳本 `install.ps1` 一鍵部署，對應 Linux 的 `install.sh`。

### C-0. 前置需求（一次性）

**只需要 Docker Desktop**——憑證由腳本以 .NET 內建 X509 API 產生，不需另裝
openssl / Git for Windows。

1. **Docker Desktop**：安裝後開啟，等待右下角狀態顯示 **Running**。
   建議用 WSL2 後端（Settings → General → Use the WSL 2 based engine）。
2. **允許執行腳本**：若 PowerShell 擋下 `install.ps1`，於**目前工作階段**放行（不改全域設定）：

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

### C-1. 部署步驟

**最簡單：雙擊 `install.bat`**。它會先解除「來自網路」標記（ZIP 下載常見、
會被智慧型應用程式控制 Smart App Control 封鎖），再以正確參數呼叫
`install.ps1`，最後停在畫面等你看結果。要指定網域可在命令列：
`install.bat -Domain workflow.example.com`。

或在 PowerShell 手動執行：

```powershell
# 1) 取得程式碼
git clone https://github.com/zzx789654/workflow.git workflow
cd workflow

# 2) 一鍵部署（一般使用者即可，無需系統管理員）
.\install.ps1

# 可選：指定網域（憑證 CN 與 CORS 會用它）
.\install.ps1 -Domain workflow.example.com
```

> **ZIP 下載 + 雙擊 `.ps1` 被封鎖？** 下載 ZIP 解壓的檔案帶「網路標記」，
> 雙擊 `.ps1` 也不是執行方式（預設是編輯）。用 `install.bat`（已自動解標記），
> 或在 PowerShell 先跑 `Get-ChildItem -Recurse | Unblock-File` 再 `.\install.ps1`。

腳本依序（與 `install.sh` 等價、冪等可重跑）：

1. 偵測 Docker Desktop 是否安裝且 daemon 已啟動、`docker compose` 可用。
2. 建立 `.env`：以 .NET 亂數產生 `SECRET_KEY` / `SETTINGS_ENCRYPT_KEY`，
   設定資料庫密碼與管理員密碼（留空自動產生強密碼）；以 UTF-8（無 BOM）寫出。
3. 以 .NET 內建 X509 API 產生自簽 TLS 憑證（匯出 PFX），透過一次性 Alpine 容器
   轉成 PEM 並注入 `<專案>_certs_data` volume（憑證產生不需主機裝 openssl）。
4. `docker compose -f docker-compose.prod.yml -p <專案> up -d --build` 建置並啟動。
5. 等待後端健康檢查（`https://localhost/health`），印出存取資訊。

完成後瀏覽 `https://localhost/`（或 `https://<本機 IP>/`）。

> **架構與方式 A 完全相同**（見 [A-2. 架構](#a-2-架構)）：只有 nginx 對外，
> DB/Redis/backend 都在 compose 內網；憑證放共享 volume，可於前端設定頁熱更換。

### C-2. 日常維運（PowerShell）

```powershell
# 服務狀態 / 日誌（<專案> 為資料夾名，預設 workflow）
docker compose -f docker-compose.prod.yml -p workflow ps
docker compose -f docker-compose.prod.yml -p workflow logs -f
docker compose -f docker-compose.prod.yml -p workflow logs -f backend

# 停止 / 啟動
docker compose -f docker-compose.prod.yml -p workflow down
docker compose -f docker-compose.prod.yml -p workflow up -d

# 更新版本（拉新程式碼後重建）
git pull
docker compose -f docker-compose.prod.yml -p workflow up -d --build

# 資料庫備份 / 還原（容器名 workflow-db-1，可用 docker ps 確認）
docker exec workflow-db-1 pg_dump -U workflow workflow_db > "backup_$(Get-Date -Format yyyy-MM-dd).sql"
Get-Content backup_2026-06-10.sql | docker exec -i workflow-db-1 psql -U workflow -d workflow_db
```

### C-3. Windows 疑難排解

| 症狀 | 處理 |
|------|------|
| `install.ps1` 無法執行（被擋） | 先執行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| 腳本報「Docker daemon 未回應」 | 開啟 Docker Desktop，等狀態列顯示 Running 再重跑 |
| 憑證注入步驟失敗 | 確認 Docker daemon 正常（轉檔在一次性 Alpine 容器內進行）；`docker pull alpine` 測試可連 registry |
| `https://localhost` 連不上 | `... -p workflow ps` 看服務是否 Up；`logs nginx` 看憑證是否存在 |
| 改了 `.env` 沒生效 | 需 `down` 再 `up -d`（重建容器才會讀新環境變數） |
| 80/443 被占用 | 關閉占用該埠的程式（如 IIS、其他 nginx），或改 compose 對外埠 |

> 方式 C 與方式 A 產出的 `.env`、憑證、volume 結構一致，
> 同一台主機切換 Linux/Windows 維運不需重建資料。

---

## 方式 B — Ubuntu 裸機部署（非 Docker）

apt 原生 PostgreSQL/Redis + systemd uvicorn + 原生 nginx，部署在 `/opt/workflow`。

### B-1. 部署步驟

```bash
# 1) 取得程式碼
git clone https://github.com/zzx789654/workflow.git workflow
cd workflow

# 2) 全自動部署（需 sudo；零互動、密碼自動產生、完成印出 admin 密碼）
sudo ./install-native.sh --auto

# 指定對外網域（自簽憑證 SAN 會用到）
sudo WF_AUTO=1 DOMAIN=workflow.example.com ./install-native.sh

# 自帶密碼（搭配自動化編排，免互動也免「自動產生」）
sudo WF_DB_PASSWORD=... WF_ADMIN_PASSWORD=... WF_ADMIN_EMAIL=admin@example.com \
     DOMAIN=example.com ./install-native.sh
```

腳本依序（冪等，可重複執行）：

1. 檢查環境（root / Ubuntu 版本 / openssl）。
2. apt 安裝 PostgreSQL / Redis / Python / Node.js 20 / nginx（已裝則跳過）。
3. 建立系統使用者 `workflow`（無登入 shell）與部署目錄 `/opt/workflow`。
4. rsync 程式到 `/opt/workflow`（保留 .env / certs / uploads / venv）。
5. 產生 `.env`（強密鑰；密碼自動產生或由環境變數提供）。
6. 設定 PostgreSQL 角色 `workflow` 與資料庫 `workflow_db`。
7. 建立 Python venv 並 `pip install -r requirements.txt`。
8. `alembic upgrade head` 跑 migration。
9. `npm ci && npm run build` build 前端。
10. 產生自簽 TLS 憑證。
11. 修正權限（程式 root 擁有、執行期資料 workflow 擁有、私鑰 0600）。
12. 佈署 systemd units + nginx 設定，啟動服務。
13. 等待健康檢查，印出存取網址與 admin 密碼。

完成後瀏覽 `https://<主機>/`。

### B-2. 架構

```
              ┌─────────── Ubuntu 主機 ───────────┐
瀏覽器 ─443─> │ nginx (443)                        │
              │  ├─ /          → /opt/workflow/frontend/dist
              │  ├─ /api,/ws   → 127.0.0.1:8000 (反向代理)
              │  └─ 憑證        → /opt/workflow/certs
              │ workflow-backend.service (systemd)  │
              │  └─ uvicorn :8000（非 root、只聽 127.0.0.1）
              │       ├─ PostgreSQL (localhost:5432) │
              │       └─ Redis      (localhost:6379) │
              │ workflow-cert-reload.path (systemd)  │
              │  └─ 監看憑證變更 → nginx -s reload    │
              └──────────────────────────────────────┘
```

後端只聽 `127.0.0.1`，僅 nginx 可達。憑證熱重載走 systemd path unit（監看 key.pem
→ 獨立 oneshot service `nginx -s reload`），backend 不需提權。

### B-3. 日常維運

```bash
# 服務狀態 / 日誌
systemctl status workflow-backend
journalctl -u workflow-backend -f
journalctl -u nginx -f

# 重啟 / 重載
systemctl restart workflow-backend
systemctl reload nginx

# 資料庫備份 / 還原（系統 PostgreSQL）
sudo -u postgres pg_dump workflow_db > backup_$(date +%F).sql
sudo -u postgres psql -d workflow_db < backup_2026-06-10.sql

# 更新版本（冪等，沿用既有 .env / 憑證）
cd /path/to/workflow && git pull && sudo ./install-native.sh --auto
```

### B-4. 裸機疑難排解

| 症狀 | 處理 |
|------|------|
| `https://...` 連不上 | `systemctl status nginx`；`nginx -t` 驗設定 |
| 後端不健康 | `journalctl -u workflow-backend -n 50`；常見為 DB 連線或 migration 失敗 |
| 後端啟動即 crash 報 `$HOME` 權限 | systemd 已設 `Environment=HOME=/opt/workflow`，確認該行存在 |
| 改了 `.env` 沒生效 | `systemctl restart workflow-backend`（重讀 EnvironmentFile） |

---

## 首次登入（兩種方式通用）

- **登入帳號**：管理員 Email 的 `@` 前綴（預設 `admin`，例：`admin@localhost` → `admin`）。
- **密碼**：部署時隨機產生，於安裝輸出印出（`登入密碼：…`），亦存於 `.env` 的
  `FIRST_SUPERADMIN_PASSWORD`。

> 管理者帳號由後端首次啟動自動建立（冪等，已存在不重建）；`APP_ENV=production` 會
> 拒絕以弱／預設密碼啟動，因此生產環境不會留下弱預設帳號。
>
> **首次登入後請立即改密碼**（設定 → 修改密碼）；改密碼會使所有舊 token 立即失效。

---

## 認證方式（本地 / LDAP / RADIUS）

預設本地帳號。要接公司目錄：以 admin 登入 → **設定 → 系統設定** → 將「認證方式」改為
LDAP / Active Directory 或 RADIUS，填參數後用「測試遠端認證」確認。

- 設為遠端後，登入會**先試遠端、失敗再退回本地密碼**。
- 本地帳號（含 admin）永遠能用本地密碼登入，不被同名遠端帳號鎖住。
- 遠端帳號首次登入自動建立，並帶入目錄 Email。

---

## 更換 TLS 憑證（兩種方式通用）

自簽憑證會觸發瀏覽器「不安全」告警（正常現象）。拿到 CA 簽署的正式憑證後：

1. 以 admin 登入 → **設定 → 系統設定 → TLS 憑證**。
2. 上傳憑證檔（cert.pem）與私鑰檔（key.pem，未加密），或直接貼上 PEM。
3. 按「上傳並套用」。系統驗證 cert/key 相符且未過期後，**自動熱重載 nginx**（約 5 秒生效）。

> 驗證會擋下不相符、已過期、格式錯誤的檔案。私鑰只寫入伺服器內部、權限 0600，
> 不回傳、不寫日誌。Docker 與裸機兩種方式皆支援此熱換流程。

---

## 本機開發

```bash
cp .env.example .env          # 填入開發用設定
docker compose up -d          # 起 db / redis / backend / frontend

# 後端（另開終端，需本機 Python 3.12）
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 前端
cd frontend && npm install && npm run dev
```

預設開發前端 `http://localhost:5173`、後端 `http://localhost:8000`。

---

## 測試

```bash
# 後端單元/整合測試（覆蓋率 97%）
cd backend && pytest --cov=app

# 部署後端到端功能煙霧測試（打運行中的 HTTPS 入口）
HOME=/opt/workflow .venv/bin/python tests/smoke_e2e.py \
  --base https://localhost --admin-pass '<admin_password>'
```

---

## 套件版本

兩種部署方式所需的 OS、系統套件、Python / 前端套件的**確切版本與對照表**，
見 [VERSIONS.md](VERSIONS.md)。專案中心思想與設計原則見 [CoreMain.md](CoreMain.md)。
