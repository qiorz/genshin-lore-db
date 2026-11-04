$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& "$root\tools\python\python.exe" "$PSScriptRoot\app.py" --host 127.0.0.1 --port 8765
