<#
.SYNOPSIS
  WorkFlow 一鍵部署腳本（Windows + Docker Desktop）。

.DESCRIPTION
  install.sh 的 Windows 對應版：偵測 Docker Desktop → 產生 .env 與自簽憑證
  → 注入 certs volume → docker compose 啟動 → 等待健康檢查。
  與 install.sh 產出的 .env / 憑證 / volume 結構完全一致，可互換維運。

.PARAMETER Domain
  對外網域（憑證 CN 與 CORS 會用它）。預設 localhost。

.EXAMPLE
  PS> .\install.ps1
  PS> .\install.ps1 -Domain workflow.example.com

.NOTES
  需先安裝並啟動 Docker Desktop（含 compose）。重複執行為冪等：
  已存在的 .env 會沿用，不覆寫。請以一般使用者執行即可，無需系統管理員。
#>
[CmdletBinding()]
param(
    [string]$Domain = "localhost"
)

# 本腳本以 $LASTEXITCODE + Die() 自行控制流程；native 工具（openssl/docker）會把
# 進度寫到 stderr，在 Windows PowerShell 5.1 下若用 Stop 會被誤判為致命錯誤，故用
# Continue，由各步驟自行檢查結果。
$ErrorActionPreference = "Continue"

# ── 樣式 ──────────────────────────────────────────────────────
function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Blue }
function Write-Ok($m)   { Write-Host "[ OK ] $m" -ForegroundColor Green }
function Write-WarnMsg($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Die($m) { Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

$RepoDir     = $PSScriptRoot
$EnvFile     = Join-Path $RepoDir ".env"
$ComposeFile = Join-Path $RepoDir "docker-compose.prod.yml"

# compose 專案名：取目錄名、轉小寫、只留 a-z0-9（與 install.sh 一致）
$Project = ((Split-Path $RepoDir -Leaf).ToLower() -replace '[^a-z0-9]', '')
$Volume  = "${Project}_certs_data"

# ── 0. 前置檢查 ───────────────────────────────────────────────
if (-not (Test-Path $ComposeFile)) { Die "找不到 $ComposeFile，請在專案根目錄執行" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Die "找不到 docker。請先安裝 Docker Desktop：https://www.docker.com/products/docker-desktop/"
}
# 確認 Docker daemon 已啟動（Docker Desktop 有開）
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Die "Docker daemon 未回應。請開啟 Docker Desktop 並等待狀態列顯示『Running』後重試。"
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Die "docker compose 不可用，請更新 Docker Desktop（內含 compose v2）" }
Write-Ok "Docker Desktop 與 compose 已就緒"
# 憑證以 .NET 內建 X509 API 產生（見步驟 3），故 Windows 上只需 Docker Desktop，
# 不再依賴 openssl / Git for Windows。

# ── 工具：產生強密鑰 / 密碼 ───────────────────────────────────
function New-Secret {
    # 等同 openssl rand -hex 32
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $_.ToString("x2") })
}
function New-StrongPassword {
    $bytes = New-Object byte[] 18
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $b64 = [Convert]::ToBase64String($bytes) -replace '[/+=]', ''
    ($b64.Substring(0, [Math]::Min(20, $b64.Length))) + "A1"
}
function Read-SecretOrGenerate($prompt) {
    # 空輸入則自動產生一組強密碼（對應 install.sh 的 prompt_secret_pw）。
    # 回傳物件含 Generated 旗標：唯有「本次自動產生」的密碼才會在結尾回顯，
    # 使用者自訂的密碼不回顯（避免無謂洩漏）。
    $sec = Read-Host -AsSecureString "$prompt（留空自動產生）"
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    if ([string]::IsNullOrEmpty($plain)) {
        return [pscustomobject]@{ Value = (New-StrongPassword); Generated = $true }
    }
    return [pscustomobject]@{ Value = $plain; Generated = $false }
}

# ── 2. 產生 .env（含強密鑰）────────────────────────────────────
# 供完成提示使用：本次若自動產生 admin 密碼，於結尾明確印出帳號與密碼。
$GeneratedAdminEmail = $null
$GeneratedAdminPass  = $null
if (Test-Path $EnvFile) {
    Write-WarnMsg ".env 已存在，沿用現有設定（如需重設請先備份並刪除）"
} else {
    Write-Info "建立 .env（自動產生 SECRET_KEY / SETTINGS_ENCRYPT_KEY）…"
    $DbPass     = (Read-SecretOrGenerate "設定資料庫密碼").Value
    $AdminCred  = Read-SecretOrGenerate "設定管理員(admin)密碼"
    $AdminPass  = $AdminCred.Value
    $AdminEmail = Read-Host "管理員 Email（預設 admin@$Domain）"
    if ([string]::IsNullOrWhiteSpace($AdminEmail)) { $AdminEmail = "admin@$Domain" }

    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $envContent = @"
# 由 install.ps1 於 $now 產生。請勿提交版控。
POSTGRES_USER=workflow
POSTGRES_PASSWORD=$DbPass
POSTGRES_DB=workflow_db

SECRET_KEY=$(New-Secret)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=https://$Domain

APP_ENV=production
FIRST_SUPERADMIN_EMAIL=$AdminEmail
FIRST_SUPERADMIN_PASSWORD=$AdminPass

SETTINGS_ENCRYPT_KEY=$(New-Secret)
"@
    # 以 UTF-8（無 BOM）寫出，確保 docker compose / Linux 容器可正確讀取
    [System.IO.File]::WriteAllText($EnvFile, $envContent, (New-Object System.Text.UTF8Encoding($false)))
    Write-Ok ".env 已建立"

    if ($AdminCred.Generated) {
        # 僅在「本次自動產生」時記下，供結尾回顯（使用者自訂的密碼不回顯）
        $GeneratedAdminEmail = $AdminEmail
        $GeneratedAdminPass  = $AdminPass
    }
}

# ── 3. 產生自簽憑證並注入 certs volume ────────────────────────
# 改用 .NET 內建 X509 API 產生憑證（Windows 不需 openssl/Git）。Windows PowerShell
# 5.1（.NET Framework）沒有 ExportCertificatePem / ExportPkcs8PrivateKey，故先匯出
# 成 PFX，再於注入用的一次性 Alpine 容器內以其自帶 openssl 轉成 cert.pem + key.pem。
$CertDir = Join-Path ([System.IO.Path]::GetTempPath()) ("wf_cert_" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
try {
    Write-Info "產生自簽 TLS 憑證（CN=$Domain，825 天）…"
    $pfxPath = Join-Path $CertDir "cert.pfx"
    # PFX 暫時密碼（只在主機→容器轉檔的瞬間使用，轉完即丟）
    $pfxPass = New-Secret

    $rsa = [System.Security.Cryptography.RSA]::Create(2048)
    try {
        $dn = New-Object System.Security.Cryptography.X509Certificates.X500DistinguishedName "CN=$Domain"
        $req = New-Object System.Security.Cryptography.X509Certificates.CertificateRequest `
            $dn, $rsa,
            ([System.Security.Cryptography.HashAlgorithmName]::SHA256),
            ([System.Security.Cryptography.RSASignaturePadding]::Pkcs1)

        # SubjectAltName：$Domain + localhost（瀏覽器/工具以 SAN 驗主機名）
        $san = New-Object System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder
        $san.AddDnsName($Domain)
        if ($Domain -ne "localhost") { $san.AddDnsName("localhost") }
        $req.CertificateExtensions.Add($san.Build())

        $notBefore = [System.DateTimeOffset]::UtcNow.AddDays(-1)
        $notAfter  = [System.DateTimeOffset]::UtcNow.AddDays(825)
        $cert = $req.CreateSelfSigned($notBefore, $notAfter)

        $pfxBytes = $cert.Export(
            [System.Security.Cryptography.X509Certificates.X509ContentType]::Pfx, $pfxPass)
        [System.IO.File]::WriteAllBytes($pfxPath, $pfxBytes)
        $cert.Dispose()
    }
    finally {
        $rsa.Dispose()
    }
    if (-not (Test-Path $pfxPath)) { Die "產生自簽憑證失敗" }
    Write-Ok "自簽憑證已產生"

    # 用一次性容器把 PFX 轉成 PEM 並寫入 named volume（容器自帶 openssl，主機免裝）
    Write-Info "建立並注入 certs volume（$Volume）…"
    docker volume create $Volume | Out-Null
    # 路徑轉成 Docker Desktop 可掛載格式（-v 需正斜線）
    $CertDirMount = ($CertDir -replace '\\', '/')
    $convert = "apk add --no-cache openssl >/dev/null 2>&1 && " +
               "openssl pkcs12 -in /src/cert.pfx -passin pass:$pfxPass -clcerts -nokeys -out /certs/cert.pem && " +
               "openssl pkcs12 -in /src/cert.pfx -passin pass:$pfxPass -nocerts -nodes -out /certs/key.pem && " +
               "chmod 600 /certs/key.pem"
    docker run --rm -v "${Volume}:/certs" -v "${CertDirMount}:/src:ro" alpine:latest `
        sh -c $convert *> $null
    if ($LASTEXITCODE -ne 0) { Die "PFX 轉 PEM / 注入 volume 失敗" }
    Write-Ok "憑證已注入 volume"
}
finally {
    Remove-Item -Recurse -Force $CertDir -ErrorAction SilentlyContinue
}

# ── 4. 啟動服務 ───────────────────────────────────────────────
Write-Info "建置並啟動服務（docker compose up -d --build）…"
docker compose -f $ComposeFile -p $Project up -d --build
if ($LASTEXITCODE -ne 0) { Die "docker compose 啟動失敗，請查看上方輸出" }

# ── 5. 等待後端健康檢查 ───────────────────────────────────────
# 用 Windows 10/11 內建的 curl.exe（-k 略過自簽憑證）：它能正確協商 TLS，
# 不受 Windows PowerShell 5.1 預設 .NET TLS 協定版本限制（Invoke-WebRequest 在
# 5.1 下常與 nginx 協商失敗）。首次部署含建表，故最多等 180 秒。
Write-Info "等待後端就緒（最多 180 秒，首次部署含建表較久）…"
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-WarnMsg "找不到 curl.exe，略過自動健康檢查（請手動瀏覽 https://localhost/health 確認）"
}
$ready = $false
foreach ($i in 1..60) {
    $code = & curl.exe -sk -o NUL -w "%{http_code}" --max-time 5 "https://localhost/health" 2>$null
    if ($code -eq "200") { $ready = $true; break }
    Start-Sleep -Seconds 3
}
if ($ready) {
    Write-Ok "後端已就緒"
} else {
    Write-WarnMsg "健康檢查逾時，請查看：docker compose -p $Project logs backend"
}

# ── 6. 完成提示 ───────────────────────────────────────────────
Write-Host ""
Write-Ok "部署完成"
Write-Host @"

  存取網址：   https://$Domain/   （或 https://<本機 IP>/）
"@

if ($GeneratedAdminPass) {
    # 本次自動產生密碼 → 明確印出帳號與密碼（之後請立即登入改密碼）
    $loginUser = if ($GeneratedAdminEmail -match "@") { $GeneratedAdminEmail.Split("@")[0] } else { $GeneratedAdminEmail }
    Write-Host ""
    Write-Host "  ┌─ 管理員登入資訊（本次自動產生，請妥善保存）─────────" -ForegroundColor Cyan
    Write-Host "  │  登入帳號：$loginUser" -ForegroundColor Cyan
    Write-Host "  │  登入密碼：$GeneratedAdminPass" -ForegroundColor Cyan
    Write-Host "  │  （亦存於專案根目錄 .env 的 FIRST_SUPERADMIN_PASSWORD）" -ForegroundColor Cyan
    Write-Host "  └────────────────────────────────────────────────────" -ForegroundColor Cyan
    Write-WarnMsg "首次登入後請立即修改密碼（設定 → 修改密碼）。"
} else {
    Write-Host @"
  管理員帳號： 部署時設定的 Email @ 前綴為登入帳號（例：admin@$Domain → admin）
               密碼存於專案根目錄 .env 的 FIRST_SUPERADMIN_PASSWORD
"@
}

Write-Host @"

[WARN] 自簽憑證提醒
  瀏覽器首次連線會顯示「不安全」告警，這是自簽憑證的正常現象。
  正式環境請於  設定 → 系統設定 → TLS 憑證  上傳由 CA 簽署的憑證，
  上傳後 nginx 會自動熱重載，約 5 秒生效。

[WARN] 資料備份提醒
  資料庫存於 Docker named volume「${Project}_postgres_data」。
  定期備份：docker exec ${Project}-db-1 pg_dump -U workflow workflow_db > backup.sql

  常用指令（PowerShell）：
    查看狀態   docker compose -f docker-compose.prod.yml -p $Project ps
    查看日誌   docker compose -f docker-compose.prod.yml -p $Project logs -f
    停止服務   docker compose -f docker-compose.prod.yml -p $Project down
"@
