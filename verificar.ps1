# Verificación del entorno (FR-002): estado de cada dependencia y qué hacer si falla.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()  # acentos correctos
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) {
    Write-Host 'No existe el entorno de Python (.venv).' -ForegroundColor Red
    Write-Host 'Qué hacer: ejecuta .\instalar.ps1' -ForegroundColor Yellow
    exit 1
}
& $py -m src.entorno
exit $LASTEXITCODE
