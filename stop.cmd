@echo off
setlocal EnableExtensions
rem ============================================================
rem  关闭「原神世界观数据库」Web UI（8765）
rem    双击本文件即可；只结束 python 进程，误杀别的程序会先提示
rem    命令行加 /nopause 供脚本调用
rem ============================================================

set "PORT=8765"
set "FOUND="

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
    set "FOUND=1"
    tasklist /FI "PID eq %%p" /NH 2>nul | findstr /i "python.exe" >nul && (
        taskkill /PID %%p /F >nul 2>&1
        if errorlevel 1 (
            echo [警告] 无法结束 PID %%p（可能需要管理员权限）
        ) else (
            echo 已停止 PID %%p
        )
    ) || (
        echo [警告] 端口 %PORT% 被非 Python 进程占用（PID %%p），未处理
    )
)

if not defined FOUND echo 服务未在运行（端口 %PORT% 没有监听）

if /i not "%~1"=="/nopause" pause
exit /b 0
