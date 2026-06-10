# 部署版本與步驟（Ubuntu 原生 / Docker）

本文列出兩種部署方式所需的**套件版本**與**部署步驟**。
版本號為實際驗證環境（Ubuntu 24.04.4 @ 192.168.99.178）與專案鎖定檔（requirements.txt /
package.json / docker-compose.prod.yml）的真實值。

---

## 一、Ubuntu 原生部署（非 Docker）

由 `install-native.sh` 自動安裝，以下為其安裝並驗證過的版本。

### 作業系統

| 項目 | 版本 |
|------|------|
| OS | Ubuntu 24.04 LTS（noble）— 已驗證 24.04.4 |
| Kernel | 6.8.x generic |
| 架構 | x86_64（amd64） |

> 腳本對非 24.04 會 warn 但仍嘗試執行；正式環境建議用 24.04 LTS。

### 系統套件（apt 安裝）

| 套件 | 版本（Ubuntu 24.04 倉庫） | 用途 |
|------|--------------------------|------|
| postgresql / postgresql-contrib | **16.14**（PostgreSQL 16） | 資料庫 |
| redis-server | **7.0.15** | 快取（目前程式預留，未實際使用） |
| python3 / python3-venv / python3-dev | **3.12.3** | 後端執行環境 |
| nginx | **1.24.0** | HTTPS 反向代理 + SPA 靜態檔 |
| nodejs（NodeSource） | **20.20.2**（Node 20.x LTS）+ npm 10.8.2 | 前端 build |
| build-essential / libpq-dev | 24.04 預設 | 編譯 Python C 擴充（asyncpg/psycopg2） |
| openssl | 3.0.13 | 產生密鑰與自簽憑證 |

> Node.js 走 NodeSource 20.x 倉庫（Ubuntu 內建版本過舊）；腳本偵測到無 node 或
> 版本 < 18 時自動加入 NodeSource 來源安裝。

### Python 套件（venv，requirements.txt 鎖定）

| 套件 | 版本 |
|------|------|
| fastapi | 0.136.3 |
| uvicorn[standard] | 0.34.3 |
| sqlalchemy[asyncio] | 2.0.36 |
| asyncpg | 0.31.0 |
| psycopg2-binary | 2.9.10 |
| alembic | 1.14.0 |
| pydantic[email] / pydantic-settings | 2.10.3 / 2.6.1 |
| PyJWT | 2.13.0 |
| passlib[bcrypt] / bcrypt | 1.7.4 / 4.0.1 |
| cryptography | 46.0.7 |
| slowapi | 0.1.9 |
| ldap3 / pyrad | 2.9.1 / 2.4 |
| greenlet | 3.2.3 |

完整清單見 [backend/requirements.txt](backend/requirements.txt)。

### 前端套件（package-lock.json 鎖定）

| 套件 | 版本 |
|------|------|
| react / react-dom | 18.3.1 |
| react-router-dom | 6.28.0 |
| vite | 6.0.5 |
| typescript | 5.7.2 |
| tailwindcss | 3.4.17 |
| zustand | 5.0.2 |
| axios | 1.7.9 |

### 部署步驟

```bash
# 1. 取得專案
git clone https://github.com/zzx789654/workflow.git
cd workflow

# 2. 全自動部署（需 root；零互動、密碼自動產生）
sudo ./install-native.sh --auto
#   或指定對外網域：
sudo WF_AUTO=1 DOMAIN=workflow.example.com ./install-native.sh
```

腳本依序執行（冪等，可重複跑）：

1. **檢查環境** — 確認 root、Ubuntu 版本、openssl
2. **apt 安裝** — postgresql / redis / python / nodejs 20 / nginx（已裝則跳過）
3. **建立系統使用者** `workflow`（無登入 shell）與部署目錄 `/opt/workflow`
4. **同步程式** 到 `/opt/workflow`（rsync，保留 .env / certs / uploads / venv）
5. **產生 `.env`** — 強密鑰（openssl rand）；密碼自動產生或由環境變數提供
6. **設定 PostgreSQL** — 建立 `workflow` 角色與 `workflow_db` 資料庫
7. **建立 venv** 並 `pip install -r requirements.txt`
8. **跑 migration** — `alembic upgrade head`（18 個版本）
9. **build 前端** — `npm ci`（有 lockfile）→ `npm run build`（tsc + vite）
10. **產生自簽 TLS 憑證**（CN=DOMAIN，825 天）
11. **修正權限** — 程式 root 擁有、執行期資料 workflow 擁有、私鑰 0600
12. **佈署 systemd units + nginx 設定**，啟動服務
13. **等待健康檢查** 通過，印出存取網址與 admin 密碼

完成後：`https://<主機>/`。架構與維運見 [DEPLOY-native.md](DEPLOY-native.md)。

---

## 二、Docker 部署

由 `install.sh` 安裝 Docker 後以 `docker-compose.prod.yml` 啟動。

### 環境需求

| 項目 | 版本 |
|------|------|
| OS | Ubuntu 24.04 LTS（其他 Linux 發行版可，install.sh 針對 Ubuntu） |
| Docker Engine | 由 Docker 官方 apt 倉庫安裝最新穩定版（docker-ce / docker-ce-cli / containerd.io） |
| Docker Compose | V2 外掛（docker-compose-plugin），用 `docker compose`（非 `docker-compose`） |
| Buildx | docker-buildx-plugin |

### 容器映像版本（docker-compose.prod.yml）

| 服務 | 映像 | 說明 |
|------|------|------|
| db | **postgres:16-alpine** | 資料庫（不對外開 port） |
| redis | **redis:7-alpine** | 快取（不對外開 port） |
| backend | 由 `backend/Dockerfile` build，基底 **python:3.12-slim** | uvicorn，內網 |
| nginx | 由 `frontend/Dockerfile` build，production 階段 **nginx:alpine** | HTTPS 唯一入口（80/443） |
| reloader | **docker:cli** | 監看憑證變更熱重載 nginx 的極小 sidecar |

> 前端 build 階段用 **node:20-alpine**，產物交給 nginx:alpine 服務。
> 後端與前端的 Python/Node 套件版本同上方原生部署的鎖定表。

### 部署步驟

```bash
# 1. 取得專案
git clone https://github.com/zzx789654/workflow.git
cd workflow

# 2. 一鍵部署（需 root）
sudo ./install.sh
#   或指定對外網域：
sudo DOMAIN=workflow.example.com ./install.sh
```

腳本依序執行：

1. **檢查環境** — root、Ubuntu 版本、openssl、compose 檔存在
2. **安裝 Docker Engine + compose 外掛**（Docker 官方 apt 倉庫，冪等）
3. **產生 `.env`** — 強密鑰（openssl rand），互動詢問或自動產生 DB/admin 密碼
4. **產生自簽 TLS 憑證**，以一次性容器寫入 `certs_data` named volume
5. **`docker compose -f docker-compose.prod.yml up -d --build`** — build 並啟動全部服務
6. **等待後端健康檢查** 通過

完成後：`https://<主機>/`。架構與維運見 [DEPLOY.md](DEPLOY.md)。

---

## 兩種方式比較

| | 原生（install-native.sh） | Docker（install.sh） |
|---|---|---|
| 相依 | apt 系統套件 + Python venv | 只需 Docker Engine |
| 隔離 | systemd 服務隔離 + 強化 | 容器隔離 |
| 資源 | 較省（無容器層） | 較方便（環境一致、易遷移） |
| 升級 | `git pull` + 重跑腳本 | 重 build image |
| 適用 | 單機長期運行、想用系統原生服務 | 多環境一致、想要容器化 |

兩者皆：nginx 唯一對外（80/443）、DB/Redis/backend 不暴露、強密鑰自動產生、
APP_ENV=production 擋弱密碼、自簽憑證可經前端設定頁熱換 CA 憑證。
