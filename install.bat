@echo off
REM ============================================================
REM  WorkFlow Windows Docker deploy launcher (double-clickable)
REM
REM  Double-click this file to deploy. It:
REM    1) unblocks the project files (removes the "downloaded from
REM       the internet" Mark-of-the-Web that Smart App Control blocks)
REM    2) runs install.ps1 with ExecutionPolicy Bypass for this run only
REM
REM  Pass args through, e.g.:  install.bat -Domain workflow.example.com
REM ============================================================

setlocal
set "SCRIPT_DIR=%~dp0"

echo [WorkFlow] Unblocking project files (Mark-of-the-Web)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -LiteralPath '%SCRIPT_DIR%' -Recurse -File | Unblock-File"

echo [WorkFlow] Launching install.ps1 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo [WorkFlow] Done. See messages above for the access URL and admin login.
) else (
  echo [WorkFlow] install.ps1 exited with code %RC%. Check the messages above.
)

echo.
pause
endlocal
