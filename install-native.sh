#!/usr/bin/env bash
# WorkFlow 原生一鍵部署腳本（Ubuntu 24.04，非 Docker）
#
# 架構：apt 原生服務（PostgreSQL + Redis）+ Python venv（uvicorn，systemd）
#       + 前端 Vite build 靜態檔 + 原生 nginx（HTTPS 反向代理）。
#       憑證熱重載走 systemd path unit（取代 Docker reloader sidecar）。
#
# 用法：
#   sudo ./install-native.sh                    # 互動式（DOMAIN 預設 localhost）
#   sudo DOMAIN=workflow.local ./install-native.sh
#
# 需以 root / sudo 執行。重複執行為冪等（已完成的步驟會跳過）。

set -euo pipefail

# ── 樣式 ──────────────────────────────────────────────────────
info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; }
die()   { err "$*"; exit 1; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN="${DOMAIN:-localhost}"

# 部署目標（原生標準位置）
APP_DIR="/opt/workflow"
APP_USER="workflow"
CERT_DIR="${APP_DIR}/certs"
UPLOAD_DIR="${APP_DIR}/uploads"
ENV_FILE="${APP_DIR}/.env"
VENV_DIR="${APP_DIR}/backend/.venv"

DB_NAME="workflow_db"
DB_USER="workflow"

# ── 0. 前置檢查 ───────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || die "請以 root 或 sudo 執行：sudo ./install-native.sh"

if [ -r /etc/os-release ]; then
  # shellcheck source=/dev/null
  . /etc/os-release
  info "偵測到系統：${PRETTY_NAME:-unknown}"
  case "${VERSION_ID:-}" in
    24.04) ok "Ubuntu 24.04，符合目標環境" ;;
    *)     warn "本腳本針對 Ubuntu 24.04 測試；其他版本可能需調整" ;;
  esac
fi

[ -d "${REPO_DIR}/backend" ] || die "找不到 ${REPO_DIR}/backend，請在專案根目錄執行"
[ -d "${REPO_DIR}/frontend" ] || die "找不到 ${REPO_DIR}/frontend，請在專案根目錄執行"
[ -f "${REPO_DIR}/deploy/native/workflow-backend.service" ] || die "找不到 deploy/native/ 設定，請確認專案完整"

# ── 1. 安裝系統套件（冪等）────────────────────────────────────
install_packages() {
  info "安裝系統套件（postgresql / redis / python / nodejs / nginx）…"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq \
    postgresql postgresql-contrib \
    redis-server \
    python3 python3-venv python3-dev \
    build-essential libpq-dev \
    nginx openssl curl ca-certificates gnupg
  # Node.js（前端 build 需要）：若系統無 node 或版本過舊，裝 NodeSource 20.x
  if ! command -v node >/dev/null 2>&1 || [ "$(node -v 2>/dev/null | sed 's/v\([0-9]*\).*/\1/')" -lt 18 ]; then
    info "安裝 Node.js 20.x（NodeSource）…"
    install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/nodesource.gpg ]; then
      curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    fi
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list
    apt-get update -qq
    apt-get install -y -qq nodejs
  fi
  systemctl enable --now postgresql redis-server >/dev/null 2>&1 || true
  ok "系統套件就緒（node $(node -v 2>/dev/null), $(psql --version 2>/dev/null | head -1))"
}
install_packages

# ── 2. 建立專屬系統使用者與目錄 ───────────────────────────────
setup_user_dirs() {
  if ! id "$APP_USER" >/dev/null 2>&1; then
    info "建立系統使用者 ${APP_USER}（無登入 shell）…"
    useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
  else
    ok "系統使用者 ${APP_USER} 已存在，跳過"
  fi
  mkdir -p "$APP_DIR" "$CERT_DIR" "$UPLOAD_DIR"
}
setup_user_dirs

# ── 3. 同步專案程式到部署目錄 ─────────────────────────────────
sync_code() {
  info "同步程式到 ${APP_DIR} …"
  # 不覆蓋 .env / certs / uploads / venv（保留執行期資料與密鑰）
  for sub in backend frontend deploy; do
    rsync -a --delete \
      --exclude '.venv' --exclude '__pycache__' --exclude 'node_modules' \
      --exclude 'dist' --exclude 'uploads' \
      "${REPO_DIR}/${sub}/" "${APP_DIR}/${sub}/"
  done
  ok "程式已同步"
}
sync_code

# ── 4. 產生 .env（含強密鑰）────────────────────────────────────
gen_secret() { openssl rand -hex 32; }

gen_pw() {
  # 產生一組無 URL/SQL 特殊字元的 20+ 字元強密碼（base64 去掉 /+= 與換行）
  printf '%s' "$(openssl rand -base64 18 | tr -d '/+=\n' | cut -c1-20)A1"
}

prompt_secret_pw() {
  # $1=提示字；$2=環境變數名（若已設則直接採用，供非互動自動化用）。
  # 互動且空輸入則自動產生。所有提示與換行寫 stderr，函式 stdout 只輸出純密碼，
  # 否則 `read; echo` 的換行會被 $(...) 捕捉進密碼開頭，污染 .env / DATABASE_URL。
  local prompt="$1" envname="${2:-}" val=""
  if [ -n "$envname" ] && [ -n "${!envname:-}" ]; then
    printf '%s' "${!envname}"; return
  fi
  if [ -t 0 ]; then
    read -rsp "${prompt}（留空自動產生）：" val; echo >&2
  fi
  [ -n "$val" ] || val="$(gen_pw)"
  printf '%s' "$val"
}

if [ -f "$ENV_FILE" ]; then
  warn ".env 已存在，沿用現有設定（如需重設請先備份並刪除 ${ENV_FILE}）"
  # 從既有 .env 取 DB 密碼供後續 DB 設定使用
  DB_PASS="$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
else
  info "建立 .env（自動產生 SECRET_KEY / SETTINGS_ENCRYPT_KEY）…"
  warn "資料庫密碼會進入連線 URL，自填時請避免 @ : / # ? 等 URL 特殊字元（留空自動產生則無此限制）"
  # 密碼可由環境變數 WF_DB_PASSWORD / WF_ADMIN_PASSWORD 提供（非互動自動化）；
  # 否則互動詢問，留空自動產生。
  DB_PASS="$(prompt_secret_pw '設定資料庫密碼' WF_DB_PASSWORD)"
  # 自填密碼若含 URL 保留字元，會破壞 DATABASE_URL 解析 → 擋下並要求重設
  case "$DB_PASS" in
    *[@:/#?]*) die "資料庫密碼含 URL 特殊字元（@ : / # ?），請重新執行並改用不含這些字元的密碼，或留空自動產生" ;;
  esac
  ADMIN_PASS="$(prompt_secret_pw '設定管理員(admin)密碼' WF_ADMIN_PASSWORD)"
  if [ -n "${WF_ADMIN_EMAIL:-}" ]; then
    ADMIN_EMAIL="$WF_ADMIN_EMAIL"
  elif [ -t 0 ]; then
    read -rp "管理員 Email（預設 admin@${DOMAIN}）：" ADMIN_EMAIL
    ADMIN_EMAIL="${ADMIN_EMAIL:-admin@${DOMAIN}}"
  else
    ADMIN_EMAIL="admin@${DOMAIN}"
  fi

  cat > "$ENV_FILE" <<EOF
# 由 install-native.sh 於 $(date -u +%Y-%m-%dT%H:%M:%SZ) 產生。請勿提交版控。
POSTGRES_USER=${DB_USER}
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_DB=${DB_NAME}

# 原生部署：DB/Redis 在本機，後端直連 localhost
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
REDIS_URL=redis://localhost:6379/0

SECRET_KEY=$(gen_secret)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=https://${DOMAIN}

APP_ENV=production
FIRST_SUPERADMIN_EMAIL=${ADMIN_EMAIL}
FIRST_SUPERADMIN_PASSWORD=${ADMIN_PASS}

SETTINGS_ENCRYPT_KEY=$(gen_secret)

# 原生路徑（覆寫程式預設的容器路徑）
TLS_CERT_DIR=${CERT_DIR}
UPLOAD_DIR=${UPLOAD_DIR}
EOF
  chmod 600 "$ENV_FILE"
  ok ".env 已建立（權限 600）"
fi
[ -n "${DB_PASS:-}" ] || die "無法取得資料庫密碼（.env 損壞？）"

# ── 5. 設定 PostgreSQL 角色與資料庫（冪等）────────────────────
setup_database() {
  info "設定 PostgreSQL 角色與資料庫…"
  # 密碼經 psql 變數 :'pw' 帶入（psql 自動加單引號並正確跳脫），
  # 不直接內插進 SQL 字串，避免使用者自填密碼含特殊字元造成注入或語法錯。
  # 注意：psql 的 :'var' 插值「只在 stdin / -f 檔案模式」生效，-c 字串模式不展開，
  # 故 SQL 一律經 stdin 餵入（here-string），不用 -c。
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    sudo -u postgres psql -v pw="$DB_PASS" >/dev/null <<<"ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD :'pw';"
  else
    sudo -u postgres psql -v pw="$DB_PASS" >/dev/null <<<"CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD :'pw';"
  fi
  # 資料庫：不存在則建立
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
  fi
  ok "PostgreSQL 角色 ${DB_USER} 與資料庫 ${DB_NAME} 就緒"
}
setup_database

# ── 6. 建立 Python venv 並安裝相依 ────────────────────────────
setup_backend() {
  info "建立 Python venv 並安裝後端相依…"
  if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
  fi
  "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
  "${VENV_DIR}/bin/pip" install --quiet -r "${APP_DIR}/backend/requirements.txt"
  ok "後端相依安裝完成"
}
setup_backend

# ── 7. 跑 DB migration（顯式，原生不靠 lifespan）──────────────
run_migration() {
  info "執行資料庫 migration（alembic upgrade head）…"
  (
    cd "${APP_DIR}/backend"
    set -a
    # shellcheck source=/dev/null
    . "$ENV_FILE"
    set +a
    "${VENV_DIR}/bin/alembic" upgrade head
  )
  ok "migration 完成"
}
run_migration

# ── 8. build 前端靜態檔 ───────────────────────────────────────
build_frontend() {
  info "安裝前端相依並 build（同源部署，走相對路徑）…"
  # build 需要 devDependencies（tsc / vite）。npm 在某些環境（NODE_ENV=production
  # 或 root）會 omit dev，故顯式 --include=dev --no-omit=dev 強制裝齊。
  # 不用 --silent：build 失敗時要能看到 tsc/vite 的真實錯誤。
  (
    cd "${APP_DIR}/frontend"
    export NODE_ENV=development VITE_API_URL="" VITE_WS_URL=""
    # 有 lock 檔用 npm ci（可重現）；無則用 npm install。
    # 兩者都顯式 --include=dev：build 需要 tsc / vite（devDependencies），
    # npm 在 root/production 環境會 omit dev。
    if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
      npm ci --include=dev --no-audit --no-fund
    else
      warn "frontend 無 package-lock.json，改用 npm install（建議補 lock 檔以可重現建置）"
      npm install --include=dev --no-audit --no-fund
    fi
    npm run build
  )
  [ -f "${APP_DIR}/frontend/dist/index.html" ] || die "前端 build 未產出 dist/index.html"
  ok "前端 build 完成（${APP_DIR}/frontend/dist）"
}
build_frontend

# ── 9. 產生自簽憑證（若尚無）──────────────────────────────────
setup_certs() {
  if [ -f "${CERT_DIR}/cert.pem" ] && [ -f "${CERT_DIR}/key.pem" ]; then
    ok "憑證已存在，跳過（如需重產請刪除 ${CERT_DIR}/*.pem）"
    return
  fi
  info "產生自簽 TLS 憑證（CN=${DOMAIN}，825 天）…"
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "${CERT_DIR}/key.pem" -out "${CERT_DIR}/cert.pem" \
    -days 825 -subj "/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost" 2>/dev/null
  chmod 600 "${CERT_DIR}/key.pem"
  ok "自簽憑證已產生"
}
setup_certs

# ── 10. 修正權限（程式 root 擁有、執行期資料 workflow 擁有）────
fix_permissions() {
  chown -R root:root "${APP_DIR}/backend" "${APP_DIR}/frontend" "${APP_DIR}/deploy"
  chown -R "${APP_USER}:${APP_USER}" "$UPLOAD_DIR" "$CERT_DIR"
  # venv 與 .env 由 workflow 讀取
  chown -R "${APP_USER}:${APP_USER}" "$VENV_DIR"
  chown "${APP_USER}:${APP_USER}" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  chmod 600 "${CERT_DIR}/key.pem"
  ok "權限已設定"
}
fix_permissions

# ── 11. 佈署 systemd units 與 nginx 設定 ──────────────────────
deploy_services() {
  info "佈署 systemd units 與 nginx 設定…"
  local SRC="${APP_DIR}/deploy/native"
  install -m 0644 "${SRC}/workflow-backend.service"     /etc/systemd/system/workflow-backend.service
  install -m 0644 "${SRC}/workflow-cert-reload.path"    /etc/systemd/system/workflow-cert-reload.path
  install -m 0644 "${SRC}/workflow-cert-reload.service" /etc/systemd/system/workflow-cert-reload.service

  # nginx：佈署設定、停用預設站台、啟用 workflow
  install -m 0644 "${SRC}/nginx-workflow.conf" /etc/nginx/sites-available/workflow
  ln -sf /etc/nginx/sites-available/workflow /etc/nginx/sites-enabled/workflow
  rm -f /etc/nginx/sites-enabled/default
  nginx -t || die "nginx 設定驗證失敗，請檢查 /etc/nginx/sites-available/workflow"

  systemctl daemon-reload
  systemctl enable --now workflow-backend.service >/dev/null
  systemctl enable --now workflow-cert-reload.path >/dev/null
  systemctl restart nginx
  ok "服務已啟動（workflow-backend / cert-reload.path / nginx）"
}
deploy_services

# ── 12. 等待後端健康檢查 ──────────────────────────────────────
info "等待後端就緒（最多 120 秒）…"
for i in $(seq 1 40); do
  if curl -fsk "https://localhost/health" >/dev/null 2>&1 \
     || curl -fs "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    ok "後端已就緒"
    break
  fi
  [ "$i" -eq 40 ] && { warn "健康檢查逾時，請查看：journalctl -u workflow-backend -n 50"; break; }
  sleep 3
done

# ── 13. 完成提示 ──────────────────────────────────────────────
cat <<EOF

$(ok '原生部署完成')

  存取網址：   https://${DOMAIN}/   （或 https://<本機 IP>/）
  管理員帳號： ${ADMIN_EMAIL:-（沿用既有 .env）} 的 @ 前綴為登入帳號
               例：admin@${DOMAIN} → 登入帳號 admin

$(warn '自簽憑證提醒')
  瀏覽器首次連線會顯示「不安全」告警，這是自簽憑證的正常現象。
  正式環境請於  設定 → 系統設定 → TLS 憑證  上傳由 CA 簽署的憑證，
  上傳後 cert-reload path unit 會自動重載 nginx，約 5 秒生效。

$(warn '資料備份提醒')
  資料庫由系統 PostgreSQL 管理（資料庫 ${DB_NAME}）。
  定期備份：sudo -u postgres pg_dump ${DB_NAME} > backup.sql

  常用指令：
    後端狀態   systemctl status workflow-backend
    後端日誌   journalctl -u workflow-backend -f
    重啟後端   systemctl restart workflow-backend
    nginx 日誌 journalctl -u nginx -f
EOF
