@echo off
rem Arranca todo el proyecto Lipsync 2D: la interfaz (guiones, voces, render, lote), la voz (gemini-tts-studio) y el Editor de poses,
rem y abre la interfaz en el navegador (desde ahi hay un enlace al Editor de poses).
rem Cada servicio queda en su propia ventana; cierra esa ventana para apagarlo.
setlocal
set "PROYECTO=%~dp0"
set "TTS=C:\Users\Juan 02\Desktop\gemini-tts-studio"
set "PY=%PROYECTO%.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo No encuentro el entorno de Python en "%PROYECTO%.venv". Ejecuta primero instalar.ps1
  pause
  exit /b 1
)

rem --- Editor de poses (puerto 8770) ---
netstat -ano | findstr /R /C:":8770 .*LISTENING" >nul
if errorlevel 1 (
  echo Arrancando el Editor de poses...
  start "Editor de poses (puerto 8770)" /D "%PROYECTO%" "%PY%" "prototipos\editor\servidor_editor.py" 8770
) else (
  echo El Editor de poses ya estaba encendido.
)

rem --- Voz: gemini-tts-studio (puerto 5055) ---
netstat -ano | findstr /R /C:":5055 .*LISTENING" >nul
if errorlevel 1 (
  if exist "%TTS%\.venv\Scripts\python.exe" (
    echo Arrancando gemini-tts-studio...
    start "gemini-tts-studio (puerto 5055)" /D "%TTS%" "%TTS%\.venv\Scripts\python.exe" app.py
  ) else if exist "%TTS%\start.bat" (
    echo Preparando gemini-tts-studio por primera vez...
    start "gemini-tts-studio (puerto 5055)" /D "%TTS%" cmd /k start.bat
  ) else (
    echo AVISO: no encuentro gemini-tts-studio en "%TTS%"; sin el no se genera voz desde el guion.
  )
) else (
  echo gemini-tts-studio ya estaba encendido.
)

rem --- Interfaz del proyecto (puerto 8780): guiones, voces, render y lote ---
netstat -ano | findstr /R /C:":8780 .*LISTENING" >nul
if errorlevel 1 (
  echo Arrancando la interfaz del proyecto...
  start "Interfaz del proyecto (puerto 8780)" /D "%PROYECTO%" "%PY%" -m src.ui --no-abrir --puerto 8780
) else (
  echo La interfaz ya estaba encendida.
)

echo Abriendo la interfaz en el navegador...
timeout /t 4 /nobreak >nul
start "" "http://localhost:8780/"
endlocal
