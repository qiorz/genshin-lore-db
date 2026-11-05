<#
停止「原神世界观数据库」Web UI。

    .\webui\stop.ps1                  # 停 8765
    .\webui\stop.ps1 -Port 8766       # 停指定端口

只停「确实是本库 app.py 且端口匹配」的进程；
端口被其他程序占用时会明确拒绝，不会误杀别的 Python 进程。
即使服务是手工启动、没有 PID 文件，也能按端口找到并停止。
#>
[CmdletBinding()]
param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$root    = Split-Path -Parent $PSScriptRoot
$logDir  = Join-Path $root "logs"
$pidFile = Join-Path $logDir "webui-$Port.pid"
$url     = "http://127.0.0.1:$Port/"

function Get-ListenerPid {
    param([int]$ListenPort)
    $conn = Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    foreach ($line in (netstat -ano -p TCP)) {
        if ($line -match "^\s*TCP\s+\S+:$ListenPort\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            return [int]$Matches[1]
        }
    }
    return 0
}

function Test-IsOurWebUI {
    param($ProcessInfo, [int]$ListenPort)
    if ($ProcessInfo.Name -notmatch '^python') { return $false }
    $cmd = [string]$ProcessInfo.CommandLine
    if ($cmd -notmatch 'app\.py')              { return $false }
    if ($cmd -notmatch ('--port\s+{0}\b' -f $ListenPort)) { return $false }
    return $true
}

# 候选：端口上的监听进程 + PID 文件里记的进程（兼容手工启动 / 重启后残留）
$candidates = @()
$listener = Get-ListenerPid -ListenPort $Port
if ($listener -gt 0) { $candidates += $listener }
if (Test-Path $pidFile) {
    $raw = ([string](Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)).Trim()
    if ($raw -match '^\d+$') { $candidates += [int]$raw }
}
$candidates = @($candidates | Sort-Object -Unique)

if ($candidates.Count -eq 0) {
    Write-Host "Web UI 未运行（端口 $Port 无监听，也没有 PID 文件）。" -ForegroundColor Yellow
    return
}

$stopped = @()
$refused = @()
foreach ($procId in $candidates) {
    $info = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    if (-not $info) { continue }
    if (-not (Test-IsOurWebUI -ProcessInfo $info -ListenPort $Port)) {
        $refused += $procId
        continue
    }
    Stop-Process -Id $procId -Force -Confirm:$false -ErrorAction Stop
    $stopped += $procId
}

# 等端口真正释放
for ($i = 0; $i -lt 20; $i++) {
    if ((Get-ListenerPid -ListenPort $Port) -eq 0) { break }
    Start-Sleep -Milliseconds 200
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue

if ($stopped.Count -gt 0) {
    Write-Host "Web UI 已停止：$url" -ForegroundColor Green
    Write-Host "  结束进程 PID $($stopped -join ', ')"
    $still = Get-ListenerPid -ListenPort $Port
    if ($still -gt 0) { Write-Warning "端口 $Port 仍被 PID $still 占用，请检查。" }
}
foreach ($procId in $refused) {
    $info = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    Write-Warning "拒绝停止 PID $procId：不是本库 Web UI（$([string]$info.CommandLine)）"
}
if ($stopped.Count -eq 0 -and $refused.Count -eq 0) {
    Write-Host "没有需要停止的进程（端口 $Port 上的进程已退出）。" -ForegroundColor Yellow
}
