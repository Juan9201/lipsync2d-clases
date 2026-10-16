"""Interfaces de capa y de anclas (P7): el compositor solo depende de esto, no de capas
concretas, para poder añadir en la Fase 2 una VideoLoopLayer y anclas por frame."""
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple, Union

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
    fase_ojos: str = "abierto"   # «abierto», «medio» o «cerrado» (parpadeo por imagen); sin ella vale `parpadeando`

    @property
    def ojos(self) -> str:
        """Fase de los ojos: la explícita o, si solo se indicó `parpadeando`, «cerrado»."""
        if self.fase_ojos != "abierto":
            return self.fase_ojos
        return "cerrado" if self.parpadeando else "abierto"


@dataclass(frozen=True)
class CapaRGBA:
    imagen: Image.Image   # RGBA ya escalada
    x: int                # esquina superior izquierda en el frame de salida
    y: int


class BaseLayer(Protocol):
    def renderizar(self, ctx: ContextoFrame) -> Union[None, CapaRGBA, Sequence[CapaRGBA]]:
        """Una imagen, varias (se apilan en orden) o None si la capa no se ve en este frame."""


class ProveedorAnclas(Protocol):
    def anclas(self, n_frame: int, pose: str) -> Anclas: ...
