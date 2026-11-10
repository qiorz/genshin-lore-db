@echo off
setlocal EnableExtensions
rem ============================================================
rem  启动「原神世界观数据库」Web UI（8765）
rem    双击本文件即可；已在运行则只打开浏览器
rem    命令行加 /nopause 供脚本调用
rem ============================================================

set "ROOT=%~dp0"
set "PORT=8765"
set "PY=%ROOT%tools\python\python.exe"
set "APP=%ROOT%webui\app.py"
set "LOG=%ROOT%logs\webui-%PORT%.log"

if not exist "%PY%" (
    echo [错误] 找不到便携 Python：%PY%
    goto :fail
)
if not exist "%APP%" (
    echo [错误] 找不到 webui\app.py
    goto :fail
)
if not exist "%ROOT%logs" mkdir "%ROOT%logs" >nul 2>&1

set "RUNPID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do set "RUNPID=%%p"
if defined RUNPID (
    echo 服务已在运行：http://127.0.0.1:%PORT%/  ^(PID %RUNPID%^)
    goto :open
)

echo 正在启动…（日志：logs\webui-%PORT%.log）
start "Genshin Lore DB %PORT%" /min "%PY%" "%APP%" --host 127.0.0.1 --port %PORT% --log-file "%LOG%"

set /a tries=0
:wait
set /a tries+=1
set "RUNPID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do set "RUNPID=%%p"
if defined RUNPID goto :ok
if %tries% geq 20 goto :timeout
timeout /t 1 /nobreak >nul
goto :wait

:timeout
echo [警告] 20 秒内没起来，看日志：%LOG%
goto :fail

:ok
echo 已启动：http://127.0.0.1:%PORT%/  ^(PID %RUNPID%^)

:open
if /i not "%~1"=="/nopause" (
    start "" "http://127.0.0.1:%PORT%/"
    echo.
    echo 关闭服务：双击 stop.cmd，或关掉最小化的服务窗口
    pause
)
exit /b 0

:fail
if /i not "%~1"=="/nopause" pause
exit /b 1
