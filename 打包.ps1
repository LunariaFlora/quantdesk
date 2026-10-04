$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements-dev.txt first. See README.' }
if (-not (Test-Path -LiteralPath 'data\aapl.csv')) {
    & $python download_data.py
    if ($LASTEXITCODE -ne 0) { throw 'The real historical sample is missing.' }
}
& $python -m PyInstaller --noconfirm packaging/QuantDesk.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Write-Host 'Ready: dist\QuantDesk\QuantDesk.exe. Distribute the entire QuantDesk folder.'
