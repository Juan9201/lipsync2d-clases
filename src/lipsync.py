"""Lipsync (FR-020, FR-021, FR-022): ejecuta Rhubarb, cachea por hash del audio y suaviza
la línea de visemas para que ninguno dure menos de 2 frames (salvo cierres A)."""
import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from src import rutas
from src.audio import SIN_VENTANA, requerir
from src.errores import ErrorAccionable

VERSION_RHUBARB = "1.14.0"
RECONOCEDORES = ("phonetic", "pocketSphinx")


@dataclass(frozen=True)
class Cue:
    inicio: float
    fin: float
    valor: str


@dataclass(frozen=True)
class ResultadoLipsync:
    cues: List[Cue]
    duracion_s: float
    desde_cache: bool


def parsear_salida_rhubarb(texto: str) -> Tuple[List[Cue], float]:
    d = json.loads(texto)
    cues = [Cue(float(c["start"]), float(c["end"]), c["value"]) for c in d["mouthCues"]]
    return cues, float(d["metadata"]["duration"])


def cues_a_frames(cues: List[Cue], duracion_s: float, fps: int) -> List[str]:
    """Un visema por frame, muestreado en el centro del frame. Un cierre A más corto que un
    frame no se pierde: se fuerza en el frame que contiene su punto medio."""
    n = max(1, round(duracion_s * fps))
    inicios = np.array([c.inicio for c in cues])
    frames = []
    for i in range(n):
        t = (i + 0.5) / fps
        k = int(np.searchsorted(inicios, t, side="right")) - 1
        frames.append(cues[max(k, 0)].valor if cues else "X")
    for c in cues:
        if c.valor == "A" and c.fin - c.inicio >= 0.02:
            j = min(n - 1, int(((c.inicio + c.fin) / 2) * fps))
            frames[j] = "A"
    return frames


def suavizar(frames: List[str], min_frames: int = 2) -> List[str]:
    """Absorbe en el vecino más largo todo tramo < min_frames, salvo los cierres A (FR-022)."""
    tramos: List[List] = []
    for v in frames:
        if tramos and tramos[-1][0] == v:
            tramos[-1][1] += 1
        else:
            tramos.append([v, 1])
    i = 0
    while i < len(tramos):
        valor, largo = tramos[i]
        if largo < min_frames and valor != "A" and len(tramos) > 1:
            prev = tramos[i - 1] if i > 0 else None
            sig = tramos[i + 1] if i + 1 < len(tramos) else None
            if prev is not None and (sig is None or prev[1] >= sig[1]):
                prev[1] += largo
                tramos.pop(i)
                i -= 1
            else:
                sig[1] += largo
                tramos.pop(i)
            # fusionar vecinos iguales que hayan quedado juntos
            j = max(i - 1, 0)
            while j + 1 < len(tramos):
                if tramos[j][0] == tramos[j + 1][0]:
                    tramos[j][1] += tramos[j + 1][1]
                    tramos.pop(j + 1)
                else:
                    j += 1
            i = max(j - 1, 0) if i >= len(tramos) else max(i - 1, 0)
        else:
            i += 1
    return [v for v, largo in tramos for _ in range(largo)]


def _hash_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def analizar(wav: Path, rhubarb: Optional[Path] = None, cache_dir: Optional[Path] = None,
             dialogo: Optional[str] = None, reconocedor: str = "phonetic") -> ResultadoLipsync:
    """Analiza un WAV 16 kHz mono (ver audio.convertir_para_analisis) con Rhubarb."""
    if reconocedor not in RECONOCEDORES:
        raise ErrorAccionable(f"Reconocedor desconocido «{reconocedor}»",
                              f"Usa uno de: {', '.join(RECONOCEDORES)}")
    wav = Path(wav)
    clave = hashlib.sha256("|".join([
        _hash_archivo(wav), reconocedor, hashlib.sha256((dialogo or "").encode("utf-8")).hexdigest(),
        VERSION_RHUBARB]).encode()).hexdigest()[:32]
    archivo_cache = Path(cache_dir) / "rhubarb" / f"{clave}.json" if cache_dir else None
    if archivo_cache and archivo_cache.is_file():
        d = json.loads(archivo_cache.read_text(encoding="utf-8"))
        return ResultadoLipsync([Cue(*c) for c in d["cues"]], d["duracion"], True)

    rhubarb = requerir(rhubarb or rutas.RHUBARB)
    with tempfile.TemporaryDirectory(prefix="rhubarb_") as tmp:
        tmp = Path(tmp)
        salida = tmp / "salida.json"
        cmd = [str(rhubarb), "-f", "json", "--extendedShapes", "GHX", "-r", reconocedor, "-o", str(salida)]
        if dialogo and dialogo.strip():
            ruta_dialogo = tmp / "dialogo.txt"
            ruta_dialogo.write_text(dialogo, encoding="utf-8")
            cmd += ["--dialogFile", str(ruta_dialogo)]
        cmd.append(str(wav))
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=SIN_VENTANA)
        if r.returncode != 0 or not salida.is_file():
            detalle = (r.stderr or r.stdout or "").strip()[-300:]
            raise ErrorAccionable(f"Rhubarb falló al analizar {wav.name} ({detalle})",
                                  "Comprueba que el audio no esté dañado y ejecuta .\\verificar.ps1")
        cues, duracion = parsear_salida_rhubarb(salida.read_text(encoding="utf-8"))
    if archivo_cache:
        archivo_cache.parent.mkdir(parents=True, exist_ok=True)
        archivo_cache.write_text(json.dumps({"duracion": duracion, "cues": [[c.inicio, c.fin, c.valor] for c in cues]}),
                                 encoding="utf-8")
    return ResultadoLipsync(cues, duracion, False)
