Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'data/aapl.csv')) {
    python download_data.py
    if ($LASTEXITCODE -ne 0) { Write-Host 'Sample download failed. You can still import a CSV.' }
}
Write-Host 'Open http://127.0.0.1:8765 in your browser. Ctrl+C stops the server.'
python server.py
