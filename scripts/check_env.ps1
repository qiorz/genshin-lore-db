#requires -Version 5.1
<#
.SYNOPSIS
    Check the local toolchain for Genshin Lore DB.

.DESCRIPTION
    Verifies Python, SQLite/FTS5, optional Python packages, git, and the
    schema files. Does not install anything and does not modify the database.

.EXAMPLE
    pwsh -File scripts/check_env.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Write-Check {
    param([string]$Status, [string]$Message)
    Write-Host ("[{0}] {1}" -f $Status, $Message)
}

Write-Host "== Genshin Lore DB environment check =="
Write-Host "Project: $root"
Write-Host ""

# --- Portable SQLite CLI (optional but useful without Python) ----------------
$portableSqlite = Join-Path $root 'tools\sqlite\sqlite3.exe'
if (Test-Path -LiteralPath $portableSqlite) {
    $sqliteVersion = & $portableSqlite --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Check 'OK' "Portable SQLite CLI: $sqliteVersion"
    }
    else {
        Write-Check 'WARN' 'Portable SQLite CLI exists but did not run.'
        $warnings.Add('Portable SQLite CLI did not run.')
    }
}
else {
    Write-Check 'INFO' 'No portable SQLite CLI under tools/sqlite/.'
}

# --- Python -----------------------------------------------------------------
$python = $null
$portablePython = Join-Path $root 'tools\python\python.exe'
if (Test-Path -LiteralPath $portablePython) {
    $python = Get-Command $portablePython -ErrorAction SilentlyContinue
}
if (-not $python) {
    foreach ($name in @('python', 'python3', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        if ($cmd.Source -like '*\WindowsApps\*') {
            $warnings.Add("Skipping Windows Store alias: $($cmd.Source)")
            continue
        }
        $python = $cmd
        break
    }
}

if (-not $python) {
    Write-Check 'FAIL' 'Python not found (or only the Windows Store alias exists).'
    Write-Host ''
    Write-Host 'Install a portable Python under tools/python/ (recommended), or install Python 3.10+ system-wide.'
    Write-Host 'Then install: requests beautifulsoup4 markdownify PyYAML jieba jsonschema mwparserfromhell'
    exit 1
}

Write-Check 'OK' "Python executable: $($python.Source)"
$versionText = & $python.Source --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Check 'FAIL' "Python did not run: $versionText"
    exit 1
}
Write-Check 'OK' "$versionText"

# --- Core Python checks ------------------------------------------------------
$coreCode = @'
import sys
import sqlite3

ok = True
print(f"Python version: {sys.version.split()[0]}")
print(f"SQLite version: {sqlite3.sqlite_version}")

if sys.version_info < (3, 10):
    print("Python 3.10+ is required.")
    ok = False

try:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(x)")
    print("FTS5: OK")
except Exception as exc:
    print(f"FTS5: FAIL ({exc})")
    ok = False

sys.exit(0 if ok else 2)
'@

$coreOutput = $coreCode | & $python.Source - 2>&1
$coreExit = $LASTEXITCODE
$coreOutput | ForEach-Object { Write-Host $_ }
if ($coreExit -ne 0) {
    $failures.Add('Python core/SQLite/FTS5 check failed.')
}

# --- Optional packages -------------------------------------------------------
Write-Host ''
Write-Host 'Optional Python packages:'
$packages = @('requests', 'bs4', 'markdownify', 'yaml', 'jieba', 'jsonschema', 'mwparserfromhell')
$missing = @()
foreach ($pkg in $packages) {
    & $python.Source -c "import $pkg" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Check 'OK' $pkg
    }
    else {
        Write-Check 'MISSING' $pkg
        $missing += $pkg
    }
}
if ($missing.Count -gt 0) {
    $warnings.Add("Missing Python packages: $($missing -join ', ')")
}

# --- Schema smoke test -------------------------------------------------------
Write-Host ''
Write-Host 'Schema smoke test:'
$schemaCode = @'
import sys
import sqlite3
from pathlib import Path

root = Path(sys.argv[1])
con = sqlite3.connect(":memory:")
con.execute("PRAGMA foreign_keys = ON")

try:
    con.executescript((root / "schema" / "schema.sql").read_text(encoding="utf-8"))
    print("schema.sql: OK")
except Exception as exc:
    print(f"schema.sql: FAIL ({exc})")
    sys.exit(3)

try:
    con.executescript((root / "schema" / "fts.sql").read_text(encoding="utf-8"))
    print("fts.sql: OK")
except Exception as exc:
    print(f"fts.sql: FAIL ({exc})")
    sys.exit(4)

con.close()
'@

$schemaOutput = $schemaCode | & $python.Source - $root 2>&1
$schemaExit = $LASTEXITCODE
$schemaOutput | ForEach-Object { Write-Host $_ }
if ($schemaExit -ne 0) {
    $failures.Add('Schema smoke test failed.')
}

# --- Git and files -----------------------------------------------------------
Write-Host ''
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVersion = git --version 2>&1
    Write-Check 'OK' $gitVersion
}
else {
    Write-Check 'WARN' 'git not found (version control is recommended).'
    $warnings.Add('git not found.')
}

foreach ($relative in @('README.md', 'schema/schema.sql', 'schema/fts.sql')) {
    $path = Join-Path $root $relative
    if (Test-Path $path) {
        Write-Check 'OK' "Found $relative"
    }
    else {
        Write-Check 'FAIL' "Missing $relative"
        $failures.Add("Missing $relative")
    }
}

$docsDir = Join-Path $root 'docs'
if ((Test-Path $docsDir) -and @(Get-ChildItem -LiteralPath $docsDir -Filter '*.md' -File).Count -gt 0) {
    Write-Check 'OK' 'docs/ contains Markdown design documents'
}
else {
    Write-Check 'FAIL' 'docs/ has no Markdown files'
    $failures.Add('docs/ has no Markdown files')
}

# --- Summary -----------------------------------------------------------------
Write-Host ''
Write-Host '== Summary =='
if ($warnings.Count -gt 0) {
    Write-Host 'Warnings:'
    $warnings | ForEach-Object { Write-Host "  - $_" }
}
if ($failures.Count -gt 0) {
    Write-Host 'Failures:'
    $failures | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

Write-Host 'Core checks passed.'
if ($missing.Count -gt 0) {
    Write-Host "Install optional packages: $($python.Source) -m pip install $($missing -join ' ')"
}
Write-Host 'Next: fetch/render/load a document, then run scripts/search.py.'
exit 0
