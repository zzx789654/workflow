# WorkFlow 原生部署指南（Ubuntu 24.04，非 Docker）

本指南說明如何在 Ubuntu 24.04 主機上**原生**部署 WorkFlow（不使用 Docker）。
若你想用 Docker 部署，請改看 [DEPLOY.md](DEPLOY.md)。

## 架構

```
                    ┌─────────── Ubuntu 24.04 主機 ───────────┐
  使用者 ──HTTPS──▶ │  nginx (443)                            │
                    │   ├─ /          → /opt/workflow/frontend/dist (SPA 靜態檔)
                    │   ├─ /api/, /ws → 127.0.0.1:8000 (反向代理)
                    │   └─ TLS 憑證    → /opt/workflow/certs/{cert,key}.pem
                    │                                          │
                    │  workflow-backend.service (systemd)      │
                    │   └─ uvicorn app.main:app :8000 (workers 2，非 root)
                    │        ├─ PostgreSQL (localhost:5432)    │
                    │        └─ Redis      (localhost:6379)    │
                    │                                          │
                    │  workflow-cert-reload.path (systemd)     │
                    │   └─ 監看憑證變更 → nginx -s reload       │
                    └──────────────────────────────────────────┘
```

- **對外**：只有 nginx 的 80/443。後端只聽 `127.0.0.1:8000`，不對外。
- **資料庫**：系統 PostgreSQL（資料庫 `workflow_db`，角色 `workflow`）。
- **Redis**：系統 redis-server（目前程式未實際使用，預留）。
- **應用**：部署在 `/opt/workflow`，後端以非 root 系統使用者 `workflow` 執行。

## 一鍵安裝

在乾淨的 Ubuntu 24.04 主機上：

```bash
# 1. 取得專案（git clone 或 scp 上傳）
git clone <repo-url> workflow && cd workflow

# 2a. 全自動部署（零互動，所有密碼自動產生，完成後印出 admin 密碼）
sudo ./install-native.sh --auto
sudo WF_AUTO=1 DOMAIN=workflow.example.com ./install-native.sh

# 2b. 互動式（會詢問 DB/admin 密碼，留空則自動產生）
sudo ./install-native.sh
sudo DOMAIN=workflow.example.com ./install-native.sh

# 2c. 自帶密碼（搭配自動化編排，免互動也免「自動產生」）
sudo WF_DB_PASSWORD=... WF_ADMIN_PASSWORD=... WF_ADMIN_EMAIL=admin@example.com \
     DOMAIN=example.com ./install-native.sh
```

> **全自動模式**：`--auto`、`WF_AUTO=1`，或在無 tty 環境（CI / SSH 管線）下會自動啟用。
> 不詢問任何問題；密碼若未由環境變數提供則自動產生強密碼，並在**部署完成時印出
> admin 登入密碼**（請立即保存，之後可登入後於設定頁修改，密碼亦存於 `/opt/workflow/.env`）。

腳本會（冪等，可重複執行）：
1. apt 安裝 PostgreSQL / Redis / Python / Node.js 20 / nginx
2. 建立系統使用者 `workflow` 與部署目錄 `/opt/workflow`
3. rsync 程式到 `/opt/workflow`（保留 .env / certs / uploads / venv）
4. 產生 `.env`（強密鑰；首次互動詢問 DB/admin 密碼，留空自動產生）
5. 設定 PostgreSQL 角色與資料庫
6. 建立 Python venv 並安裝相依
7. `alembic upgrade head` 跑 migration
8. `npm ci && npm run build` build 前端
9. 產生自簽 TLS 憑證
10. 修正權限（程式 root 擁有、執行期資料 workflow 擁有、私鑰 0600）
11. 佈署 systemd units 與 nginx 設定、啟動服務
12. 等待後端健康檢查

完成後瀏覽 `https://<主機>/`，以 admin email 的 `@` 前綴為登入帳號（例：`admin@localhost` → 帳號 `admin`）。

## 管理者帳號

後端首次啟動時會自動建立一個管理者帳號（`role=admin`、`auth_source=local`），冪等——
已存在則不重建、不覆蓋。

- **登入帳號**：`FIRST_SUPERADMIN_EMAIL` 的 `@` 前綴（預設 `admin`）。
- **密碼**：**不是固定預設值**，而是部署時隨機產生的強密碼，於安裝輸出印出
  （`登入密碼：…`），亦存於 `/opt/workflow/.env` 的 `FIRST_SUPERADMIN_PASSWORD`。
  可改用 `WF_ADMIN_PASSWORD` 環境變數自帶。
- **防呆**：`APP_ENV=production` 時 `validate_production_secrets()` 會拒絕以弱／預設
  密碼（如 `admin123456`）啟動，因此生產環境不會留下弱預設帳號。

> **首次登入後請立即改密碼**：登入 → 設定 → 修改密碼。改密碼會使該帳號**所有舊
> token 立即失效**（token_version 機制），等同強制重新登入，安全性更高。改完即可
> 將 `/opt/workflow/.env` 中的 `FIRST_SUPERADMIN_PASSWORD` 視為歷史值（之後以資料庫
> 內的新密碼為準）。

## 安全設計（延續 G06/G07）

- **最小權限**：後端以非 root `workflow` 執行；systemd 強化（`NoNewPrivileges` / `ProtectSystem=strict` / `MemoryDenyWriteExecute` / `RestrictAddressFamilies` 等）。
- **後端不對外**：`--host 127.0.0.1`，僅 nginx 可達。
- **憑證熱重載無提權**：前端上傳憑證 → 後端原子寫入 `certs/` → `workflow-cert-reload.path` 偵測 `key.pem` 變更 → 獨立 oneshot service 跑 `nginx -t && nginx -s reload`。後端**不需** sudo、不碰 nginx（取代 Docker 版的 docker.sock sidecar）。
- **強密鑰**：`SECRET_KEY` / `SETTINGS_ENCRYPT_KEY` 用 `openssl rand -hex 32`；`APP_ENV=production` 觸發 `validate_production_secrets()` 擋弱密鑰。
- **檔案權限**：`.env` 與 `key.pem` 為 0600。
- **nginx 安全標頭**：nosniff / X-Frame-Options DENY / HSTS / Referrer-Policy。

## 常用維運指令

```bash
# 服務狀態 / 日誌
systemctl status workflow-backend
journalctl -u workflow-backend -f
journalctl -u nginx -f

# 重啟
systemctl restart workflow-backend
systemctl reload nginx

# 資料庫備份
sudo -u postgres pg_dump workflow_db > backup-$(date +%F).sql

# 更新程式後重新部署（冪等，沿用既有 .env / 憑證）
cd /path/to/workflow && git pull && sudo ./install-native.sh
```

## TLS 憑證更換

正式環境請用 CA 簽署的憑證：登入後到 **設定 → 系統設定 → TLS 憑證**，上傳 cert/key，
後端驗證（cert/key 相符、未過期）後原子寫入，`cert-reload.path` 自動重載 nginx，約 5 秒生效。

## 已知風險 / 待實機驗證

- 本腳本於 Windows 開發機僅能做靜態驗證（bash -n、shellcheck 0 警告、unit 結構、nginx 大括號平衡）；
  **完整流程、冪等性、健康檢查需在目標 Ubuntu 24.04 實機驗證**。
- `MemoryDenyWriteExecute=true` 在極少數含 JIT 的相依下可能導致後端啟動失敗；
  若 `journalctl -u workflow-backend` 出現相關錯誤，移除該行重啟即可（已知最高風險項）。
- 自簽憑證會觸發瀏覽器告警（預期）；上傳 CA 憑證後消除。
