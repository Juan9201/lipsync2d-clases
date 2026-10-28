# Enciende todo lo que necesita la producción, SEPARADO de la ventana o la sesión que lo lanza (si esa se cierra, esto sigue):
#   voz (5055) · herramienta de subtítulos: API (8001) y web (3003) · interfaz (8780)
# Con -Lote también reanuda el render de lo pendiente (2 trabajadores) y el proceso que subtitula y publica en Drive.
# Lo que ya esté encendido no se vuelve a lanzar. Uso:   powershell -ExecutionPolicy Bypass -File iniciar_todo.ps1 [-Lote] [-Trabajadores 2]
param([switch]$Lote, [int]$Trabajadores = 2)

$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $proyecto ".venv\Scripts\python.exe"
$voz = "C:\Users\Juan 02\Desktop\gemini-tts-studio"
$subs = "C:\AI CC-gsap"

function Escuchando([int] $puerto) { return [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue) }

# Win32_Process.Create deja el proceso fuera del árbol de quien lo lanza: no muere cuando esa ventana o sesión termina.
function Lanzar([string] $nombre, [string] $carpeta, [string] $comando) {
    $inicio = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]7 }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = "cmd.exe /c `"set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& $comando`""
        CurrentDirectory = $carpeta
        ProcessStartupInformation = $inicio }
    if ($r.ReturnValue -ne 0) { Write-Host "  ! no se pudo lanzar $nombre (código $($r.ReturnValue))" } else { Write-Host "  + $nombre lanzado (pid $($r.ProcessId))" }
}

function Servicio([string] $nombre, [int] $puerto, [string] $carpeta, [string] $comando) {
    if (Escuchando $puerto) { Write-Host "  = $nombre ya está encendido ($puerto)"; return }
    Lanzar $nombre $carpeta $comando
}

Write-Host "Encendiendo servicios..."
Servicio "voz (gemini-tts-studio)" 5055 $voz "`"$voz\.venv\Scripts\python.exe`" app.py"
Servicio "subtítulos API" 8001 "$subs\backend" "`"$subs\backend\.venv\Scripts\uvicorn.exe`" app.main:app --host 127.0.0.1 --port 8001"
Servicio "subtítulos web" 3003 "$subs\frontend" "set NEXT_DIST_DIR=.next-3003&& `"C:\Program Files\nodejs\npm.cmd`" run dev -- -p 3003"
Servicio "interfaz del proyecto" 8780 $proyecto "`"$py`" -m src.ui --no-abrir --puerto 8780"

if ($Lote) {
    Start-Sleep -Seconds 12
    Write-Host "Reanudando el lote..."
    # las clases que quedaron «en proceso» de una ejecución interrumpida vuelven solas a la cola cuando el lote arranca
    $hay = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'src\.lote correr' }
    if ($hay) { Write-Host "  = el lote ya está corriendo" } else { Lanzar "lote de render ($Trabajadores trabajadores)" $proyecto "`"$py`" -m src.lote correr --trabajadores $Trabajadores" }
    $hay = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'src\.publicar correr' }
    if ($hay) { Write-Host "  = el proceso de subtítulos y Drive ya está corriendo" } else { Lanzar "subtítulos y Drive" $proyecto "`"$py`" -m src.publicar correr" }
}
Write-Host "Listo. Panel: http://localhost:8780/"
