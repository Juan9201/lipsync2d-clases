"""Codificador (FR-031, FR-032, FR-033): recibe frames RGB por stdin hacia ffmpeg y escribe
el MP4 de forma atómica (.part.mp4 -> nombre final solo si todo salió bien)."""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from src import rutas
from src.audio import SIN_VENTANA, info_audio, requerir
from src.errores import ErrorAccionable

TOLERANCIA_DURACION_S = 0.15


class Codificador:
    def __init__(self, final: Path, audio: Path, ancho: int, alto: int, fps: int = 25,
                 ffmpeg: Optional[Path] = None, ffprobe: Optional[Path] = None,
                 duracion_esperada_s: Optional[float] = None, crf: int = 23,
                 preset: str = "veryfast"):
        self.final = Path(final)
        self.parcial = self.final.with_name(self.final.stem + ".part.mp4")
        self.audio = Path(audio)
        self.ancho, self.alto, self.fps = ancho, alto, fps
        self.ffmpeg = requerir(ffmpeg or rutas.FFMPEG)
        self.ffprobe = requerir(ffprobe or rutas.FFPROBE)
        self.duracion_esperada_s = duracion_esperada_s
        self.crf, self.preset = crf, preset
        self._proceso: Optional[subprocess.Popen] = None
        self._errores = None
        self._bytes_frame = ancho * alto * 3

    # ---- ciclo de vida ----
    def __enter__(self) -> "Codificador":
        self.final.parent.mkdir(parents=True, exist_ok=True)
        self.parcial.unlink(missing_ok=True)
        audio_cmd = ["-c:a", "copy"] if self.audio.suffix.lower() == ".mp3" else ["-c:a", "aac", "-b:a", "192k"]
        cmd = [str(self.ffmpeg), "-v", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{self.ancho}x{self.alto}",
               "-r", str(self.fps), "-i", "-", "-i", str(self.audio),
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf), "-pix_fmt", "yuv420p",
               *audio_cmd, "-movflags", "+faststart", "-f", "mp4", str(self.parcial)]
        self._errores = tempfile.TemporaryFile()
        self._proceso = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                         stderr=self._errores, bufsize=0, creationflags=SIN_VENTANA)
        return self

    def escribir(self, frame_rgb: bytes) -> None:
        if len(frame_rgb) != self._bytes_frame:
            raise ValueError(f"El frame tiene {len(frame_rgb)} bytes y se esperaban {self._bytes_frame} "
                             f"({self.ancho}x{self.alto} RGB)")
        vista = memoryview(frame_rgb)
        try:
            while vista:
                escritos = self._proceso.stdin.write(vista)
                vista = vista[escritos:]
        except (BrokenPipeError, OSError) as exc:
            raise ErrorAccionable(
                f"ffmpeg se detuvo durante el render: {self._leer_errores()}",
                "Revisa el audio y el espacio libre en disco, y vuelve a lanzar la clase") from exc

    def __exit__(self, tipo, valor, tb) -> bool:
        if tipo is not None:
            self._abortar()
            return False
        try:
            self._proceso.stdin.close()
        except OSError:
            pass
        codigo = self._proceso.wait()
        if codigo != 0:
            mensaje = self._leer_errores()
            self._abortar()
            raise ErrorAccionable(f"ffmpeg terminó con error ({mensaje})",
                                  "Revisa el audio y el espacio libre en disco, y vuelve a lanzar la clase")
        try:
            self._validar()
        except Exception:
            self._abortar()
            raise
        self._cerrar_errores()
        os.replace(self.parcial, self.final)    # atómico en el mismo volumen
        return False

    # ---- internos ----
    def _validar(self) -> None:
        esperada = self.duracion_esperada_s
        if esperada is None:
            esperada = info_audio(self.audio, self.ffprobe).duracion_s
        r = subprocess.run([str(self.ffprobe), "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(self.parcial)], capture_output=True, text=True,
                           creationflags=SIN_VENTANA)
        try:
            real = float(r.stdout.strip())
        except ValueError as exc:
            raise ErrorAccionable("El MP4 generado no se puede leer",
                                  "Vuelve a lanzar la clase; si persiste, revisa el espacio en disco") from exc
        if abs(real - esperada) > TOLERANCIA_DURACION_S:
            raise ErrorAccionable(
                f"El video dura {real:.2f} s y se esperaban {esperada:.2f} s",
                "Vuelve a lanzar la clase; si persiste, revisa que el audio no esté dañado")

    def _leer_errores(self) -> str:
        try:
            self._errores.seek(0)
            return self._errores.read().decode("utf-8", errors="replace").strip()[-300:] or "sin detalle"
        except (OSError, ValueError):
            return "sin detalle"

    def _cerrar_errores(self) -> None:
        try:
            self._errores.close()
        except OSError:
            pass

    def _abortar(self) -> None:
        if self._proceso is not None:
            try:
                self._proceso.kill()
            except OSError:
                pass
            try:
                self._proceso.stdin.close()
            except OSError:
                pass
            self._proceso.wait()
        self._cerrar_errores()
        self.parcial.unlink(missing_ok=True)
