#!/usr/bin/env bash
# WorkFlow 一鍵部署腳本（Ubuntu 24.04）
# 安裝 Docker → 產生 .env 與自簽憑證 → docker compose 啟動 → 等待健康檢查。
#
# 用法：
#   sudo ./install.sh                 # 互動式
#   sudo DOMAIN=workflow.local ./install.sh
#
# 需以 root / sudo 執行。重複執行為冪等（已裝的步驟會跳過）。

set -euo pipefail

# ── 樣式 ──────────────────────────────────────────────────────
info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; }
die()   { err "$*"; exit 1; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REPO_DIR}/.env"
COMPOSE_FILE="${REPO_DIR}/docker-compose.prod.yml"
DOMAIN="${DOMAIN:-localhost}"

# ── 0. 前置檢查 ───────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || die "請以 root 或 sudo 執行：sudo ./install.sh"

if [ -r /etc/os-release ]; then
  . /etc/os-release
  info "偵測到系統：${PRETTY_NAME:-unknown}"
  case "${VERSION_ID:-}" in
    24.04) ok "Ubuntu 24.04，符合目標環境" ;;
    *)     warn "本腳本針對 Ubuntu 24.04 測試；其他版本可能需調整" ;;
  esac
fi

command -v openssl >/dev/null 2>&1 || die "缺少 openssl，請先 apt-get install -y openssl"
[ -f "$COMPOSE_FILE" ] || die "找不到 ${COMPOSE_FILE}，請在專案根目錄執行"

# ── 1. 安裝 Docker Engine + compose plugin（冪等）─────────────
install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    ok "Docker 與 compose plugin 已安裝，跳過"
    return
  fi
  info "安裝 Docker Engine（官方 apt repo）…"
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
  fi
  local arch codename
  arch="$(dpkg --print-architecture)"
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${codename} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  ok "Docker 安裝完成"
}
install_docker

# ── 2. 產生 .env（含強密鑰）────────────────────────────────────
gen_secret() { openssl rand -hex 32; }

prompt_secret_pw() {
  # $1=提示字；空輸入則自動產生一組強密碼
  local prompt="$1" val
  read -rsp "${prompt}（留空自動產生）：" val; echo
  if [ -z "$val" ]; then val="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)A1"; fi
  printf '%s' "$val"
}

if [ -f "$ENV_FILE" ]; then
  warn ".env 已存在，沿用現有設定（如需重設請先備份並刪除）"
else
  info "建立 .env（自動產生 SECRET_KEY / SETTINGS_ENCRYPT_KEY）…"
  DB_PASS="$(prompt_secret_pw '設定資料庫密碼')"
  ADMIN_PASS="$(prompt_secret_pw '設定管理員(admin)密碼')"
  read -rp "管理員 Email（預設 admin@${DOMAIN}）：" ADMIN_EMAIL
  ADMIN_EMAIL="${ADMIN_EMAIL:-admin@${DOMAIN}}"

  cat > "$ENV_FILE" <<EOF
# 由 install.sh 於 $(date -u +%Y-%m-%dT%H:%M:%SZ) 產生。請勿提交版控。
POSTGRES_USER=workflow
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_DB=workflow_db

SECRET_KEY=$(gen_secret)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=https://${DOMAIN}

APP_ENV=production
FIRST_SUPERADMIN_EMAIL=${ADMIN_EMAIL}
FIRST_SUPERADMIN_PASSWORD=${ADMIN_PASS}

SETTINGS_ENCRYPT_KEY=$(gen_secret)
EOF
  chmod 600 "$ENV_FILE"
  ok ".env 已建立（權限 600）"
fi

# ── 3. 產生自簽憑證並注入 certs volume ────────────────────────
CERT_DIR="$(mktemp -d)"
trap 'rm -rf "$CERT_DIR"' EXIT
info "產生自簽 TLS 憑證（CN=${DOMAIN}，825 天）…"
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "${CERT_DIR}/key.pem" -out "${CERT_DIR}/cert.pem" \
  -days 825 -subj "/CN=${DOMAIN}" \
  -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost" 2>/dev/null
chmod 600 "${CERT_DIR}/key.pem"
ok "自簽憑證已產生"

# 用一次性容器把憑證寫入 named volume（compose 專案名取目錄名）
PROJECT="$(basename "$REPO_DIR" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')"
VOLUME="${PROJECT}_certs_data"
info "建立並注入 certs volume（${VOLUME}）…"
docker volume create "$VOLUME" >/dev/null
docker run --rm -v "${VOLUME}:/certs" -v "${CERT_DIR}:/src:ro" alpine:latest \
  sh -c "cp /src/cert.pem /certs/cert.pem && cp /src/key.pem /certs/key.pem && chmod 600 /certs/key.pem"
ok "憑證已注入 volume"

# ── 4. 啟動服務 ───────────────────────────────────────────────
info "建置並啟動服務（docker compose up -d --build）…"
docker compose -f "$COMPOSE_FILE" -p "$PROJECT" up -d --build

# ── 5. 等待後端健康檢查 ───────────────────────────────────────
info "等待後端就緒（最多 120 秒）…"
for i in $(seq 1 40); do
  if curl -fsk "https://localhost/health" >/dev/null 2>&1 \
     || curl -fs "http://localhost:8000/health" >/dev/null 2>&1; then
    ok "後端已就緒"
    break
  fi
  [ "$i" -eq 40 ] && { warn "健康檢查逾時，請查看：docker compose -p ${PROJECT} logs backend"; break; }
  sleep 3
done

# ── 6. 完成提示 ───────────────────────────────────────────────
cat <<EOF

$(ok '部署完成')

  存取網址：   https://${DOMAIN}/   （或 https://<本機 IP>/）
  管理員帳號： ${ADMIN_EMAIL:-（沿用既有 .env）} 的 @ 前綴為登入帳號
               例：admin@${DOMAIN} → 登入帳號 admin

$(warn '自簽憑證提醒')
  瀏覽器首次連線會顯示「不安全」告警，這是自簽憑證的正常現象。
  正式環境請於  設定 → 系統設定 → TLS 憑證  上傳由 CA 簽署的憑證，
  上傳後 nginx 會自動熱重載，約 5 秒生效。

$(warn '資料備份提醒')
  資料庫存於 Docker named volume「${PROJECT}_postgres_data」。
  定期備份：docker exec ${PROJECT}-db-1 pg_dump -U workflow workflow_db > backup.sql

  常用指令：
    查看狀態   docker compose -f docker-compose.prod.yml -p ${PROJECT} ps
    查看日誌   docker compose -f docker-compose.prod.yml -p ${PROJECT} logs -f
    停止服務   docker compose -f docker-compose.prod.yml -p ${PROJECT} down
EOF
