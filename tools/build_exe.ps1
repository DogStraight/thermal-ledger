param(
    [string]$Out = "dist"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed --name ThermalLedger `
    --paths src `
    --add-data "src\thermal_ledger\translations;thermal_ledger\translations" `
    --distpath $Out --workpath build --specpath . launcher.py

Write-Host "Built: $Out\ThermalLedger.exe"
