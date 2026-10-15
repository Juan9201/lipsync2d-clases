"""Utilidades de prueba: audios sintéticos y recortes con ffmpeg."""
import subprocess
from pathlib import Path
from typing import Sequence

RAIZ = Path(__file__).resolve().parents[1]
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffprobe.exe"
EJEMPLO = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"


def _ffmpeg(*args) -> None:
    subprocess.run([str(FFMPEG), "-v", "error", "-y", *map(str, args)], check=True)


def recortar_audio(origen: Path, destino: Path, segundos: float, inicio: float = 0.0) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-ss", inicio, "-t", segundos, "-i", origen, "-c", "copy", "-f", "mp3", destino)
    return destino


def recodificar(origen: Path, destino: Path, rate: int, canales: int, segundos: float = 0) -> Path:
    """Reexporta con otra frecuencia de muestreo y número de canales."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    extra = ["-t", segundos] if segundos else []
    _ffmpeg("-i", origen, *extra, "-ar", rate, "-ac", canales, "-b:a", "128k", destino)
    return destino


def silencio(destino: Path, segundos: float, rate: int = 44100) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=mono", "-t", segundos, "-b:a", "128k", destino)
    return destino


def concatenar(partes: Sequence[Path], destino: Path) -> Path:
    """Une MP3 del mismo formato sin recodificar."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    lista = destino.with_name(destino.name + ".lista.txt")
    lista.write_text("".join("file '{}'\n".format(Path(p).resolve().as_posix()) for p in partes), encoding="utf-8")
    try:
        _ffmpeg("-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", destino)
    finally:
        lista.unlink(missing_ok=True)
    return destino


def duracion(ruta: Path) -> float:
    out = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(ruta)], capture_output=True, text=True, check=True).stdout
    return float(out.strip())
