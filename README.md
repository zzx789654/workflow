# WorkFlow

讓組織內部團隊，以「任務」為核心，簡單清楚地協同推進每天的工作。
打開就知道我今天要做什麼、誰在等我、哪件事卡住了。

技術棧：FastAPI + PostgreSQL + Redis + React/Vite + TailwindCSS。

---

## 自動部署

提供兩種一鍵部署方式，擇一即可。兩者都會自動產生強密鑰、建立管理者帳號，
並在完成時印出 admin 登入密碼。

### 方式一：原生部署（Ubuntu 24.04，非 Docker）

apt 原生 PostgreSQL/Redis + systemd uvicorn + nginx HTTPS。詳見 [DEPLOY-native.md](DEPLOY-native.md)。

```bash
# 取得專案
git clone https://github.com/zzx789654/workflow.git && cd workflow

# 全自動部署（零互動，所有密碼自動產生，完成後印出 admin 密碼）
sudo ./install-native.sh --auto

# 指定對外網域（自簽憑證 SAN 會用到）
sudo WF_AUTO=1 DOMAIN=workflow.example.com ./install-native.sh

# 自帶密碼（搭配自動化編排，免互動也免「自動產生」）
sudo WF_DB_PASSWORD=... WF_ADMIN_PASSWORD=... WF_ADMIN_EMAIL=admin@example.com \
     DOMAIN=example.com ./install-native.sh
```

腳本冪等（可重複執行）；完成後瀏覽 `https://<主機>/`。

### 方式二：Docker 部署

nginx(HTTPS) 為唯一對外入口，DB/Redis/backend 不對外暴露。詳見 [DEPLOY.md](DEPLOY.md)。

```bash
git clone https://github.com/zzx789654/workflow.git && cd workflow

# 一鍵部署（裝 Docker → 產 .env 與自簽憑證 → 啟動 → 健康檢查）
sudo ./install.sh

# 指定網域
sudo DOMAIN=workflow.example.com ./install.sh
```

---

## 登入

部署完成後，以管理者帳號登入：

- **登入帳號**：admin email 的 `@` 前綴（預設 `admin`，例：`admin@localhost` → `admin`）
- **密碼**：部署時隨機產生，於安裝輸出印出（`登入密碼：…`），亦存於 `.env` 的 `FIRST_SUPERADMIN_PASSWORD`

> 自簽憑證會觸發瀏覽器「不安全」告警（正常現象）。正式環境請於
> **設定 → 系統設定 → TLS 憑證** 上傳 CA 簽署的憑證，上傳後自動熱重載 nginx。
>
> **首次登入後請立即改密碼**（設定 → 修改密碼）；改密碼會使舊 token 立即失效。

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

## 文件

| 文件 | 內容 |
|------|------|
| [DEPLOY-native.md](DEPLOY-native.md) | Ubuntu 24.04 原生部署（非 Docker） |
| [DEPLOY.md](DEPLOY.md) | Docker 部署 |
| [CoreMain.md](CoreMain.md) | 專案中心思想與設計原則 |
