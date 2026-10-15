"""Rutas de las herramientas instaladas dentro del proyecto (P4, P5)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffprobe.exe"
RHUBARB = RAIZ / "herramientas" / "rhubarb" / "rhubarb.exe"
