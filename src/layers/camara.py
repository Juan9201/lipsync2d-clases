"""Cámara virtual (FR-053): cada plano es una ventana de recorte 16:9 sobre el lienzo de la
pose; el escenario y el personaje se recortan con la misma ventana, como un zoom real."""
from dataclasses import dataclass

from src.biblioteca.modelos import Pose


@dataclass(frozen=True)
class Ventana:
    x0: float
    y0: float
    w: float
    h: float

    def escala(self, ancho_salida: int) -> float:
        """Píxeles de salida por píxel de lienzo."""
        return ancho_salida / self.w


def _limitar(v: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(v, maximo))


def ventana_plano(pose: Pose, plano: str) -> Ventana:
    cfg = pose.planos[plano]               # KeyError si el plano no existe
    lw, lh = pose.lienzo
    h = cfg.alto_relativo * lh
    w = h * 16 / 9
    if w > lw:
        w, h = float(lw), lw * 9 / 16
    x0 = _limitar(pose.anclas.cabeza.x - w / 2, 0, lw - w)
    y0 = _limitar(pose.anclas.cabeza.y - cfg.centro_y_relativo * h, 0, lh - h)
    return Ventana(x0, y0, w, h)
