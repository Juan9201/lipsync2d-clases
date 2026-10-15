"""Interfaces de capa y de anclas (P7): el compositor solo depende de esto, no de capas
concretas, para poder añadir en la Fase 2 una VideoLoopLayer y anclas por frame."""
from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

from PIL import Image

from src.biblioteca.modelos import Anclas
from src.timeline import Toma


@dataclass(frozen=True)
class ContextoFrame:
    n_frame: int
    t: float
    salida: Tuple[int, int]
    toma: Optional[Toma]
    visema: str
    parpadeando: bool
    escala: float      # respiración
    dx: float          # movimiento leve, en píxeles del lienzo
    dy: float


@dataclass(frozen=True)
class CapaRGBA:
    imagen: Image.Image   # RGBA ya escalada
    x: int                # esquina superior izquierda en el frame de salida
    y: int


class BaseLayer(Protocol):
    def renderizar(self, ctx: ContextoFrame) -> Optional[CapaRGBA]: ...


class ProveedorAnclas(Protocol):
    def anclas(self, n_frame: int, pose: str) -> Anclas: ...
