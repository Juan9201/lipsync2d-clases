"""Fondo en video (FR-057, FR-058): un clip corto que se repite en bucle durante toda la clase.

Cómo se evita el salto en la unión (el clip de una calle se repite decenas de veces):
1. `preparar_bucle` crea UNA vez una «unidad de bucle»: el clip sin su último tramo, más ese
   tramo fundido (xfade) con el principio. Así el último frame de la unidad continúa de forma
   natural en el primero. Se guarda en cache/ y se reutiliza.
2. `FondoVideoLayer` lee esa unidad en streaming con ffmpeg (`-stream_loop -1`): un frame cada vez,
   ya recortado con la ventana del plano y escalado a la salida. Nunca acumula frames (P3)."""
import hashlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from src import rutas
from src.audio import SIN_VENTANA, requerir
from src.errores import AssetInvalido
from src.layers.base import CapaRGBA, ContextoFrame
from src.layers.camara import Ventana

log = logging.getLogger("fondo_video")

FUNDIDO_DEFECTO_S = 1.0
DURACION_MINIMA_S = 1.0            # menos que esto no deja un bucle útil
CRF_UNIDAD = 14                    # calidad casi sin pérdida: la unidad se vuelve a decodificar y a codificar


def _sondear(ruta: Path) -> dict:
    ffprobe = requerir(rutas.FFPROBE)
    r = subprocess.run([str(ffprobe), "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
                        str(ruta)], capture_output=True, text=True, encoding="utf-8", creationflags=SIN_VENTANA)
    try:
        datos = json.loads(r.stdout or "{}")
        video = next(s for s in datos["streams"] if s["codec_type"] == "video")
        return {"duracion": float(datos["format"]["duration"]), "ancho": int(video["width"]),
                "alto": int(video["height"])}
    except (KeyError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        raise AssetInvalido(f"No se pudo leer el video de fondo {Path(ruta).name} (¿está dañado o no es un video?)",
                            "Vuelve a exportarlo como MP4 H.264") from exc


def _huella(ruta: Path, fps: int, fundido_s: float) -> str:
    st = Path(ruta).stat()
    return hashlib.sha1(f"{Path(ruta).resolve()}|{st.st_size}|{st.st_mtime_ns}|{fps}|{fundido_s}".encode("utf-8")).hexdigest()[:12]


def _frames_de_unidad(unidad: Path, fps: int) -> int:
    ffprobe = requerir(rutas.FFPROBE)
    r = subprocess.run([str(ffprobe), "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(unidad)],
                       capture_output=True, text=True, creationflags=SIN_VENTANA)
    try:
        return int(r.stdout.strip().split()[0])
    except (ValueError, IndexError):
        return int(round(_sondear(unidad)["duracion"] * fps))


def preparar_bucle(ruta_video: Path, destino: Path, fps: int = 25, fundido_s: float = FUNDIDO_DEFECTO_S) -> int:
    """Crea (si no existe) la unidad de bucle y devuelve cuántos frames tiene.

    Con un video de duración L y un fundido D, la unidad dura L − D: [D, L−D] seguido de un
    fundido de D entre el tramo final [L−D, L] y el inicial [0, D]."""
    ruta_video, destino = Path(ruta_video), Path(destino)
    if not ruta_video.is_file():
        raise AssetInvalido(f"No existe el video de fondo {ruta_video}", "Revisa la ruta del escenario")
    info = _sondear(ruta_video)
    largo = info["duracion"]
    if largo < DURACION_MINIMA_S:
        raise AssetInvalido(f"El video de fondo {ruta_video.name} dura solo {largo:.1f} s",
                            f"Usa un video de al menos {DURACION_MINIMA_S:.0f} s (lo ideal son 10 a 20 s)")
    d = fundido_s
    if largo < 3 * d:                                    # no cabe un fundido completo con tramo medio
        d = round(largo / 3, 2)
        log.warning("El video %s dura %.1f s: el fundido de empalme se reduce de %.1f a %.2f s",
                    ruta_video.name, largo, fundido_s, d)
    marca = destino.with_suffix(".json")
    if destino.is_file() and marca.is_file():
        try:
            guardado = json.loads(marca.read_text(encoding="utf-8"))
            if guardado.get("huella") == _huella(ruta_video, fps, fundido_s):
                return int(guardado["frames"])
        except (ValueError, KeyError):
            pass
    ffmpeg = requerir(rutas.FFMPEG)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.stem + ".part.mp4")
    filtro = (f"[0:v]fps={fps},format=yuv420p,split=3[a][b][c];"
              f"[a]trim=start={d}:end={largo - d},setpts=PTS-STARTPTS[medio];"
              f"[b]trim=start={largo - d}:end={largo},setpts=PTS-STARTPTS[cola];"
              f"[c]trim=start=0:end={d},setpts=PTS-STARTPTS[cabeza];"
              f"[cola][cabeza]xfade=transition=fade:duration={d}:offset=0[unido];"
              f"[medio][unido]concat=n=2:v=1:a=0[v]")
    r = subprocess.run([str(ffmpeg), "-v", "error", "-y", "-i", str(ruta_video), "-filter_complex", filtro,
                        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", str(CRF_UNIDAD), "-preset", "fast",
                        "-pix_fmt", "yuv420p", "-r", str(fps), "-f", "mp4", str(parcial)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=SIN_VENTANA)
    if r.returncode != 0:
        parcial.unlink(missing_ok=True)
        raise AssetInvalido(f"No se pudo preparar el bucle del video {ruta_video.name}: {r.stderr.strip()[-200:]}",
                            "Revisa que el archivo sea un MP4 H.264 válido")
    parcial.replace(destino)
    frames = _frames_de_unidad(destino, fps)
    marca.write_text(json.dumps({"huella": _huella(ruta_video, fps, fundido_s), "frames": frames}), encoding="utf-8")
    return frames


class FondoVideoLayer:
    """Capa de fondo (BaseLayer) que entrega el frame `ctx.n_frame` del video en bucle, ya recortado
    con la ventana del plano y a la resolución de salida."""

    def __init__(self, ruta_video: Path, ventana: Ventana, lienzo: Tuple[int, int], salida: Tuple[int, int],
                 fps: int = 25, fundido_s: float = FUNDIDO_DEFECTO_S, desenfoque: float = 0.0,
                 cache_dir: Optional[Path] = None):
        self._salida = salida
        self._fps = fps
        self._desenfoque = desenfoque
        ruta_video = Path(ruta_video)
        cache_dir = Path(cache_dir) if cache_dir is not None else rutas.RAIZ / "cache"
        self._unidad = cache_dir / "fondos" / f"{ruta_video.stem}_{_huella(ruta_video, fps, fundido_s)}.mp4"
        self.frames_por_ciclo = preparar_bucle(ruta_video, self._unidad, fps, fundido_s)
        info = _sondear(self._unidad)
        sx, sy = info["ancho"] / lienzo[0], info["alto"] / lienzo[1]      # píxeles de video por píxel de lienzo
        self._filtro = (f"crop={ventana.w * sx:.2f}:{ventana.h * sy:.2f}:{ventana.x0 * sx:.2f}:{ventana.y0 * sy:.2f},"
                        f"scale={salida[0]}:{salida[1]}:flags=lanczos")
        if desenfoque > 0:
            self._filtro += f",gblur=sigma={desenfoque}"
        self._bytes = salida[0] * salida[1] * 3
        self._proceso: Optional[subprocess.Popen] = None
        self._proximo = 0                  # índice del próximo frame que saldrá del decodificador
        self._ultimo: Optional[CapaRGBA] = None
        self._ultimo_n = -1
        self.procesos_lanzados = 0

    # ---- decodificador ----
    def _abrir(self, desde_frame: int) -> None:
        self.cerrar()
        ffmpeg = requerir(rutas.FFMPEG)
        inicio = (desde_frame % self.frames_por_ciclo) / self._fps
        cmd = [str(ffmpeg), "-v", "error", "-stream_loop", "-1"]
        if inicio > 0:
            cmd += ["-ss", f"{inicio:.4f}"]
        cmd += ["-i", str(self._unidad), "-vf", self._filtro, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self._proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
                                         creationflags=SIN_VENTANA)
        self.procesos_lanzados += 1
        self._proximo = desde_frame

    def _leer_frame(self) -> Image.Image:
        buf = bytearray()
        while len(buf) < self._bytes:
            trozo = self._proceso.stdout.read(self._bytes - len(buf))
            if not trozo:
                raise AssetInvalido("El decodificador del video de fondo se detuvo antes de tiempo",
                                    "Revisa que el video de fondo no esté dañado")
            buf += trozo
        return Image.frombuffer("RGB", self._salida, bytes(buf), "raw", "RGB", 0, 1)

    # ---- BaseLayer ----
    def renderizar(self, ctx: ContextoFrame) -> Optional[CapaRGBA]:
        n = ctx.n_frame
        if n == self._ultimo_n and self._ultimo is not None:
            return self._ultimo
        if self._proceso is None or n != self._proximo:
            self._abrir(n)                  # primer frame o salto: se reposiciona el decodificador
        frame = self._leer_frame().convert("RGBA")
        self._proximo = n + 1
        self._ultimo, self._ultimo_n = CapaRGBA(frame, 0, 0), n
        return self._ultimo

    # ---- ciclo de vida ----
    def cerrar(self) -> None:
        if self._proceso is not None:
            try:
                self._proceso.stdout.close()
                self._proceso.terminate()
                self._proceso.wait(timeout=5)
            except Exception:
                self._proceso.kill()
            self._proceso = None

    def __enter__(self) -> "FondoVideoLayer":
        return self

    def __exit__(self, *_exc) -> None:
        self.cerrar()

    def __del__(self):
        try:
            self.cerrar()
        except Exception:
            pass
