@echo off
echo [WorkFlow] 啟動服務...

if not exist .env (
    echo [!] .env 不存在，複製 .env.example 並請填入正確設定
    copy .env.example .env
    echo [!] 請編輯 .env 後重新執行此腳本
    pause
    exit /b 1
)

echo [WorkFlow] 啟動 Docker Compose...
docker compose up --build -d

echo [WorkFlow] 等待服務就緒...
timeout /t 10 /nobreak > nul

echo.
echo =============================================
echo  WorkFlow 已啟動！
echo  後端 API:  http://localhost:8000
echo  API 文件:  http://localhost:8000/docs
echo  前端 Web:  http://localhost:5173
echo =============================================
echo.
echo 按任意鍵查看 logs (Ctrl+C 結束)
pause > nul
docker compose logs -f
