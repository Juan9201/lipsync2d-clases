"""Lectura y validación de audio, y conversión para el análisis de Rhubarb (FR-011)."""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src import rutas
from src.errores import AssetInvalido, EntornoIncompleto

EXTENSIONES = {".mp3": "mp3", ".wav": "wav"}
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class InfoAudio:
    duracion_s: float
    sample_rate: int
    canales: int
    formato: str


def requerir(binario: Path) -> Path:
    if not Path(binario).is_file():
        raise EntornoIncompleto(f"No se encontró {Path(binario).name}", "Ejecuta .\\instalar.ps1")
    return Path(binario)


def info_audio(ruta: Path, ffprobe: Path = None) -> InfoAudio:
    ruta = Path(ruta)
    ffprobe = requerir(ffprobe or rutas.FFPROBE)
    if not ruta.is_file():
        raise AssetInvalido(f"El archivo de audio no existe: {ruta}", "Revisa la ruta del audio")
    formato = EXTENSIONES.get(ruta.suffix.lower())
    if formato is None:
        raise AssetInvalido(f"Formato de audio no soportado ({ruta.suffix})",
                            "Entrega el audio en MP3 o WAV")
    r = subprocess.run([str(ffprobe), "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(ruta)], capture_output=True, text=True,
                       encoding="utf-8", creationflags=SIN_VENTANA)
    try:
        datos = json.loads(r.stdout or "{}")
        flujo = next(s for s in datos["streams"] if s["codec_type"] == "audio")
        duracion = float(datos["format"]["duration"])
        return InfoAudio(duracion, int(flujo["sample_rate"]), int(flujo["channels"]), formato)
    except (StopIteration, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise AssetInvalido(
            f"No se pudo leer el audio {ruta.name}: está dañado o no es {formato.upper()}",
            "Vuelve a exportar el audio o genera otro") from exc


def convertir_para_analisis(origen: Path, destino: Path, ffmpeg: Path = None) -> Path:
    """WAV 16 kHz mono PCM de 16 bits: lo único que Rhubarb sabe leer (no lee MP3)."""
    ffmpeg = requerir(ffmpeg or rutas.FFMPEG)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(ffmpeg), "-v", "error", "-y", "-i", str(origen), "-ar", "16000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(destino)], capture_output=True, text=True,
                       encoding="utf-8", creationflags=SIN_VENTANA)
    if r.returncode != 0:
        raise AssetInvalido(
            f"No se pudo convertir {Path(origen).name} para el análisis ({r.stderr.strip()[:200]})",
            "Comprueba que el audio no esté dañado")
    return destino
