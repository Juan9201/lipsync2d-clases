"""Línea de tiempo interna (contrato linea-de-tiempo.md): visemas, tomas y parpadeos
sobre el eje de frames del audio."""
import bisect
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Sequence

import numpy as np

from src.errores import ErrorAccionable

VISEMAS_VALIDOS = "ABCDEFGHX"


@dataclass(frozen=True)
class Visema:
    f0: int
    f1: int   # exclusivo
    v: str


@dataclass(frozen=True)
class Toma:
    f0: int
    escenario: str
    pose: str
    plano: str


@dataclass(frozen=True)
class Parpadeo:
    f0: int
    frames: int


@dataclass
class LineaDeTiempo:
    fps: int
    n_frames: int
    semilla: int
    visemas: List[Visema]
    tomas: List[Toma]
    parpadeos: List[Parpadeo] = field(default_factory=list)
    hablando: List[List[int]] = field(default_factory=list)   # [[f0, f1], ...]
    _visema_por_frame: Optional[np.ndarray] = field(default=None, init=False, repr=False, compare=False)
    _parpadeo_por_frame: Optional[np.ndarray] = field(default=None, init=False, repr=False, compare=False)

    # ---- consultas ----
    def visema_en(self, frame: int) -> str:
        if self._visema_por_frame is None:
            arr = np.full(self.n_frames, "X", dtype="<U1")
            for vis in self.visemas:
                arr[vis.f0:vis.f1] = vis.v
            self._visema_por_frame = arr
        return str(self._visema_por_frame[frame])

    def toma_en(self, frame: int) -> Toma:
        i = bisect.bisect_right([t.f0 for t in self.tomas], frame) - 1
        return self.tomas[max(i, 0)]

    def parpadeando(self, frame: int) -> bool:
        if self._parpadeo_por_frame is None:
            arr = np.zeros(self.n_frames, dtype=bool)
            for p in self.parpadeos:
                arr[p.f0:p.f0 + p.frames] = True
            self._parpadeo_por_frame = arr
        return bool(self._parpadeo_por_frame[frame])

    # ---- validación de invariantes ----
    def validar(self) -> None:
        if not self.visemas:
            raise ErrorAccionable("La línea de tiempo no tiene visemas", "Vuelve a analizar el audio")
        esperado = 0
        for vis in self.visemas:
            if vis.v not in VISEMAS_VALIDOS:
                raise ErrorAccionable(f"Visema inválido «{vis.v}» en el frame {vis.f0}",
                                      "Usa solo A, B, C, D, E, F, G, H o X")
            if vis.f0 != esperado or vis.f1 <= vis.f0:
                raise ErrorAccionable(
                    f"Los visemas no son contiguos: se esperaba empezar en el frame {esperado} "
                    f"y empieza en {vis.f0}",
                    "Vuelve a generar la línea de tiempo desde el audio")
            if vis.f1 - vis.f0 < 2 and vis.v != "A":
                raise ErrorAccionable(f"El visema {vis.v} del frame {vis.f0} dura menos de 2 frames",
                                      "Aplica el suavizado antes de validar (FR-022)")
            esperado = vis.f1
        if esperado != self.n_frames:
            raise ErrorAccionable(
                f"Los visemas cubren {esperado} frames y el video tiene {self.n_frames}",
                "Vuelve a generar la línea de tiempo desde el audio")
        if not self.tomas or self.tomas[0].f0 != 0:
            raise ErrorAccionable("La primera toma debe empezar en el frame 0",
                                  "Revisa las etiquetas del guion o las reglas del director")
        for a, b in zip(self.tomas, self.tomas[1:]):
            if b.f0 <= a.f0:
                raise ErrorAccionable(f"Las tomas no son crecientes (frames {a.f0} y {b.f0})",
                                      "Revisa las etiquetas del guion o las reglas del director")
        for p in self.parpadeos:
            if not 3 <= p.frames <= 5 or p.f0 < 0 or p.f0 + p.frames > self.n_frames:
                raise ErrorAccionable(f"El parpadeo del frame {p.f0} no cumple 3 a 5 frames dentro del video",
                                      "Vuelve a generar los parpadeos con la semilla de la clase")
        for a, b in zip(self.parpadeos, self.parpadeos[1:]):
            if not 2 * self.fps <= b.f0 - a.f0 <= 6 * self.fps:
                raise ErrorAccionable(
                    f"Los parpadeos de los frames {a.f0} y {b.f0} no están separados de 2 a 6 s",
                    "Vuelve a generar los parpadeos con la semilla de la clase")

    # ---- serialización ----
    def a_json(self) -> str:
        d = {"version": 1, "fps": self.fps, "n_frames": self.n_frames, "semilla": self.semilla,
             "visemas": [asdict(v) for v in self.visemas], "tomas": [asdict(t) for t in self.tomas],
             "parpadeos": [asdict(p) for p in self.parpadeos], "hablando": self.hablando}
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def desde_json(cls, texto: str) -> "LineaDeTiempo":
        d = json.loads(texto)
        return cls(d["fps"], d["n_frames"], d["semilla"],
                   [Visema(**v) for v in d["visemas"]], [Toma(**t) for t in d["tomas"]],
                   [Parpadeo(**p) for p in d["parpadeos"]], d.get("hablando", []))


def semilla_de_clase(clase_id: str, base: int = 0) -> int:
    """Semilla determinista derivada del identificador de la clase (FR-107)."""
    return int.from_bytes(hashlib.sha256(f"{base}:{clase_id}".encode("utf-8")).digest()[:8], "big")


def tomas_ciclicas(poses: Sequence[str], visemas: Sequence[Visema], n_frames: int, fps: int, escenario: str,
                   plano: str, duracion_toma_s: float = 25.0) -> List[Toma]:
    """Tomas provisionales (hasta que exista el director, T070): recorre las poses en orden y cambia
    cada ~`duracion_toma_s` segundos, siempre en el inicio de la pausa (visema X) más cercana (±2 s;
    sin pausa a ese alcance corta en el punto exacto). Determinista: no usa azar."""
    poses = list(poses)
    if len(poses) <= 1:
        return [Toma(0, escenario, poses[0], plano)]
    n_tomas = max(1, round(n_frames / (duracion_toma_s * fps)))
    pausas = sorted(v.f0 for v in visemas if v.v == "X" and v.f0 > 0)
    cortes = [0]
    for k in range(1, n_tomas):
        objetivo = round(k * n_frames / n_tomas)
        cercanas = [f for f in pausas if abs(f - objetivo) <= 2 * fps and f > cortes[-1]]
        corte = min(cercanas, key=lambda f: abs(f - objetivo)) if cercanas else objetivo
        if cortes[-1] < corte < n_frames:
            cortes.append(corte)
    return [Toma(f0, escenario, poses[i % len(poses)], plano) for i, f0 in enumerate(cortes)]

