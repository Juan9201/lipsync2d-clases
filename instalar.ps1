# Instalador de Lipsync 2D (FR-001, P4). Windows 10/11, PowerShell, sin permisos de administrador.
#   .\instalar.ps1                 entorno de Python + herramientas (ffmpeg, Rhubarb, Piper, voz)
#   .\instalar.ps1 -Preparacion    además el grupo opcional de preparación de assets (rembg, LaMa)
param([switch]$Preparacion)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()  # acentos correctos
$env:PYTHONUTF8 = '1'
$raiz = $PSScriptRoot
Set-Location -LiteralPath $raiz

function Falla($mensaje, $sugerencia) {
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    Write-Host "Qué hacer: $sugerencia" -ForegroundColor Yellow
    exit 1
}

# 1. Entorno de Python 3.11
$venvPython = Join-Path $raiz '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host '[1/3] Creando el entorno de Python 3.11 (.venv)...'
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        Falla 'No se encontró el lanzador de Python (py)' 'Instala Python 3.11 desde python.org y vuelve a ejecutar'
    }
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { Falla 'No se pudo crear el entorno con Python 3.11' 'Instala Python 3.11 y vuelve a ejecutar' }
}

# 2. Dependencias con versiones fijadas
Write-Host '[2/3] Instalando dependencias (versiones fijadas)...'
& $venvPython -m pip install --disable-pip-version-check -q -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { Falla 'Falló la instalación de dependencias' 'Revisa tu conexión a internet y vuelve a ejecutar' }
if ($Preparacion) {
    # Entorno aislado: LaMa exige versiones de numpy/Pillow que romperían el núcleo.
    Write-Host '      Instalando el grupo de preparación en .venv-prep (≈ 1,2 GB; puede tardar)...'
    $prepPython = Join-Path $raiz '.venv-prep\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $prepPython)) {
        & py -3.11 -m venv .venv-prep
        if ($LASTEXITCODE -ne 0) { Falla 'No se pudo crear el entorno de preparación' 'Instala Python 3.11 y vuelve a ejecutar' }
    }
    & $prepPython -m pip install --disable-pip-version-check -q -r requirements-prep.lock
    if ($LASTEXITCODE -ne 0) { Falla 'Falló la instalación del grupo de preparación' 'Revisa tu conexión y el espacio en disco' }
}

# 3. Herramientas y modelos verificados con SHA-256
Write-Host '[3/3] Descargando y verificando herramientas...'
if ($Preparacion) { & $venvPython -m src.instalador --preparacion } else { & $venvPython -m src.instalador }
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host 'Instalación terminada. Ejecuta .\verificar.ps1 para comprobar el entorno.' -ForegroundColor Green
