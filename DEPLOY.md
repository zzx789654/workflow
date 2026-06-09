# WorkFlow 部署指南（Ubuntu 24.04）

把 WorkFlow 以 HTTPS 部署到一台 Ubuntu 24.04 主機。整套服務（前端、後端、PostgreSQL、Redis、nginx）由 Docker Compose 管理，nginx 是唯一對外入口。

---

## 1. 需求

- **作業系統**：Ubuntu 24.04（其他版本可能需微調）。
- **權限**：能用 `sudo` 的帳號。
- **硬體**：建議 2 vCPU / 4 GB RAM 以上（首次會在主機上 build image，較吃資源）。
- **網路**：對外開放 **80**、**443** 連接埠（80 會自動轉址到 443）。
- 主機需能連外（下載 Docker 與基底 image）。

> 內部 100 人團隊規模，這台機器的配置已足夠。

---

## 2. 一鍵部署

```bash
# 1) 取得程式碼（擇一）
git clone <你的 repo 網址> workflow
cd workflow
# 或：把整個專案資料夾複製到主機後 cd 進去

# 2) 執行安裝腳本（會要 sudo）
sudo ./install.sh
```

可選：指定網域（憑證 CN 與 CORS 會用它）：

```bash
sudo DOMAIN=workflow.example.com ./install.sh
```

腳本會依序：

1. 檢查系統、安裝 Docker Engine + compose plugin（已裝則跳過）。
2. 建立 `.env`：自動產生 `SECRET_KEY` / `SETTINGS_ENCRYPT_KEY`，並請你設定**資料庫密碼**與**管理員密碼**（留空會自動產生強密碼）。
3. 產生**自簽 TLS 憑證**並注入憑證 volume。
4. `docker compose -f docker-compose.prod.yml up -d --build` 建置並啟動。
5. 等待後端健康檢查，印出存取資訊。

完成後以瀏覽器開啟：

```
https://<主機網域或 IP>/
```

> ⚠️ **自簽憑證**：瀏覽器首次會顯示「不安全 / 憑證無效」告警，這是自簽憑證的正常現象。點「進階 → 繼續前往」即可。要消除告警，見下方第 5 節換上正式憑證。

---

## 3. 首次登入

- **登入帳號**：是管理員 Email 的 `@` 前綴。
  例：`admin@workflow.example.com` → 登入帳號是 **`admin`**。
- **密碼**：安裝時你設定（或腳本產生）的管理員密碼。

登入後建議立即到 **設定 → 個人資料 → 變更密碼** 改一次密碼（改密碼會使舊的登入憑證失效，需重新登入）。

---

## 4. 認證方式（本地 / LDAP / RADIUS）

預設使用**本地帳號**。若要接公司目錄：

1. 以 admin 登入 → **設定 → 系統設定**。
2. 將「認證方式」改為 **LDAP / Active Directory** 或 **RADIUS**，填入主機等參數，儲存。
3. 用「測試遠端認證」確認連線。

行為說明：
- 設為 LDAP/RADIUS 後，登入會**先試遠端、失敗再退回本地密碼**。
- 本地帳號（含 admin）永遠能用本地密碼登入，不會被同名的遠端帳號鎖住。
- 遠端帳號首次登入會自動建立，並帶入目錄的 Email。

---

## 5. 更換 TLS 憑證（消除瀏覽器告警）

拿到由憑證機構（CA）或公司簽發的正式憑證後：

1. 以 admin 登入 → **設定 → 系統設定 → TLS 憑證**。
2. 上傳 **憑證檔（cert.pem）** 與 **私鑰檔（key.pem，未加密）**，可選檔案或直接貼上 PEM 內容。
3. 按「上傳並套用憑證」。系統會驗證憑證與私鑰相符且未過期，**自動熱重載 nginx**（約 5 秒生效），不需重啟服務。

驗證會擋下：憑證與私鑰不符、已過期、格式錯誤的檔案。

> 私鑰只會寫入伺服器內部、權限 0600，不會回傳或寫入日誌。

---

## 6. 日常維運

所有指令在專案根目錄執行（`<專案>` 為資料夾名，compose project 名同它）：

```bash
# 查看服務狀態
docker compose -f docker-compose.prod.yml ps

# 看即時日誌（Ctrl+C 離開）
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs -f backend   # 只看後端

# 停止 / 啟動
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 更新版本（拉新程式碼後重建）
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### 資料備份（重要）

資料庫存於 Docker named volume，**不會隨容器刪除而消失**，但仍需定期備份：

```bash
# 備份（容器名為 <專案>-db-1，可用 docker ps 確認）
docker exec <專案>-db-1 pg_dump -U workflow workflow_db > backup_$(date +%F).sql

# 還原
cat backup_2026-06-10.sql | docker exec -i <專案>-db-1 psql -U workflow -d workflow_db
```

附件檔案存於 `<專案>_uploads_data` volume；憑證存於 `<專案>_certs_data` volume。

---

## 7. 架構速覽

```
瀏覽器 ──443/HTTPS──> nginx ──┬─ /            靜態前端（SPA）
                              ├─ /api/  ────> backend:8000
                              └─ /ws    ────> backend:8000（WebSocket）
                                   backend ──> db:5432（內網）
                                            └─ redis:6379（內網）
   reloader sidecar：監看憑證變更 → 熱重載 nginx
```

- 只有 nginx 對外（80/443）；DB、Redis、backend 都在 compose 內網，不對外暴露。
- 憑證放共享 volume，前端上傳後由獨立的 reloader 觸發 nginx 重載（backend 本身不接觸 Docker，維持最小權限）。

---

## 8. 疑難排解

| 症狀 | 處理 |
|------|------|
| `https://...` 連不上 | `docker compose -f docker-compose.prod.yml ps` 看服務是否 Up；`logs nginx` 看憑證是否存在 |
| 後端一直不健康 | `logs backend`；常見為 `.env` 的 DB 密碼與 db 服務不一致，或 migration 失敗 |
| 上傳憑證失敗 | 確認 cert 與 key 相符、未過期、為未加密 PEM；錯誤訊息會指出原因 |
| 改了 `.env` 沒生效 | 需 `down` 再 `up -d`（重建容器才會讀新環境變數） |
| 想換網域 | 改 `.env` 的 `CORS_ORIGINS`，重新上傳對應網域的憑證，`up -d` |

---

## 9. 安全注意事項

- 正式環境**務必**換掉自簽憑證（第 5 節）。
- `.env` 含密鑰與密碼，權限已設 600，**切勿提交版控**。
- `APP_ENV=production` 啟動時會拒絕弱預設密鑰，請使用腳本產生的強值。
- 定期 `git pull` + `up -d --build` 取得安全更新；定期備份資料庫。
