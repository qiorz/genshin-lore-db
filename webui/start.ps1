<#
启动「原神世界观数据库」Web UI（默认后台常驻）。

    .\webui\start.ps1                  # 后台启动 8765，写好 PID 文件
    .\webui\start.ps1 -Port 8766       # 换端口
    .\webui\start.ps1 -Foreground      # 前台运行（Ctrl+C 停止，不写 PID 文件）

重复执行是安全的：如果服务已经在跑，只打印地址，不会再开一个进程。
停止请用同目录的 stop.ps1。
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$webuiDir = $PSScriptRoot
$root     = Split-Path -Parent $webuiDir
$python   = Join-Path $root "tools\python\python.exe"
$app      = Join-Path $webuiDir "app.py"
$logDir   = Join-Path $root "logs"
$pidFile  = Join-Path $logDir "webui-$Port.pid"
$url      = "http://127.0.0.1:$Port/"

if (-not (Test-Path $python)) { throw "找不到便携 Python：$python" }
if (-not (Test-Path $app))    { throw "找不到 Web UI 入口：$app" }
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

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

function Test-Health {
    try {
        $response = Invoke-WebRequest -Uri ($url + "health") -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -eq 200)
    } catch {
        return $false
    }
}

# 已经在跑：补写 PID 文件后直接返回，避免端口冲突
if (Test-Health) {
    $existingPid = Get-ListenerPid -ListenPort $Port
    if ($existingPid -gt 0) { Set-Content -Path $pidFile -Value $existingPid -Encoding ASCII }
    Write-Host "Web UI 已在运行：$url" -ForegroundColor Green
    if ($existingPid -gt 0) { Write-Host "  PID $existingPid" }
    Write-Host "  停止： .\webui\stop.ps1 -Port $Port"
    return
}

# 端口被别人的程序占了，不要盲目启动
$listener = Get-ListenerPid -ListenPort $Port
if ($listener -gt 0) {
    throw "端口 $Port 已被 PID $listener 占用，且 /health 不通（不是本库 Web UI）。可换端口： .\webui\start.ps1 -Port 8766"
}

if ($Foreground) {
    Write-Host "前台运行：$url  （Ctrl+C 停止）" -ForegroundColor Cyan
    & $python $app --host 127.0.0.1 --port $Port
    return
}

$outLog = Join-Path $logDir "webui-$Port.log"
$argLine = '"{0}" --host 127.0.0.1 --port {1} --log-file "{2}"' -f $app, $Port, $outLog

# 不用 Start-Process：部分环境同时存在 HTTPS_PROXY / https_proxy 两个大小写变体，
# Start-Process 合并环境变量时会因字典重复键抛异常。
# .NET Process.Start 直接继承父进程环境块、不构建字典，更稳；日志由 app.py 自己写文件。
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = $argLine
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
if (-not $proc.Start()) { throw "进程启动失败：$python" }
Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII

$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 300
    if (Test-Health) { $ready = $true; break }
}
if (-not $ready) {
    Write-Warning "启动后 6 秒内 /health 未就绪，日志：$outLog"
    if (Test-Path $outLog) { Get-Content $outLog -Tail 20 }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    throw "Web UI 启动失败，已清理 PID 文件"
}

Write-Host "Web UI 已启动：$url" -ForegroundColor Green
Write-Host "  PID  $($proc.Id)"
Write-Host "  日志 $outLog"
Write-Host "  停止 .\webui\stop.ps1 -Port $Port"
