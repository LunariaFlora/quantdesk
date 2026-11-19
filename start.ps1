$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$executable = Join-Path $PSScriptRoot 'dist\QuantDesk\QuantDesk.exe'
if (Test-Path -LiteralPath $executable) {
    & $executable
} else {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements.txt first. See README.' }
    & $python desktop.py
}
