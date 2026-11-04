#requires -Version 5.1
<#
.SYNOPSIS
    Search Markdown files under corpus/ without a database.

.DESCRIPTION
    A lightweight fallback while the SQLite/FTS pipeline is being built.
    Prints path:line: text for each match. Use -Regex for regular expressions.

.EXAMPLE
    powershell -File scripts/Search-Corpus.ps1 "Archon War"

.EXAMPLE
    powershell -File scripts/Search-Corpus.ps1 "Khaenri'ah|Cataclysm" -Regex
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [string]$Pattern,

    [string]$Path,

    [switch]$Regex
)

$ErrorActionPreference = 'Stop'

if (-not $Path) {
    $Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'corpus'
}

if (-not (Test-Path -LiteralPath $Path)) {
    throw "Corpus path not found: $Path"
}

$files = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Filter '*.md' -ErrorAction Stop)
if ($files.Count -eq 0) {
    Write-Host "No Markdown files under: $Path"
    Write-Host 'Add a document under corpus/ first, or pass -Path to another folder.'
    exit 0
}

$params = @{
    Path     = $files.FullName
    Pattern  = $Pattern
    Encoding = 'utf8'
}
if (-not $Regex) {
    $params['SimpleMatch'] = $true
}

$hits = @(Select-String @params)
if ($hits.Count -eq 0) {
    Write-Host "No matches for: $Pattern"
    exit 0
}

$current = (Get-Location).Path
$baseUri = [System.Uri](($current.TrimEnd('\') + '\'))
foreach ($hit in $hits) {
    $relative = [System.Uri]::UnescapeDataString(
        $baseUri.MakeRelativeUri([System.Uri]$hit.Path).ToString()
    ) -replace '/', '\'
    $line = $hit.Line.Trim()
    Write-Output ("{0}:{1}: {2}" -f $relative, $hit.LineNumber, $line)
}

Write-Host ''
Write-Host ("{0} match(es) in {1} file(s)." -f $hits.Count, ($hits.Path | Sort-Object -Unique).Count)
