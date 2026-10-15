"""Compositor (FR-030): apila capas en orden y devuelve el frame RGB. No conoce capas
concretas; solo la interfaz BaseLayer (P7)."""
from typing import Sequence, Tuple

from PIL import Image

from src.layers.base import BaseLayer, CapaRGBA, ContextoFrame


class Compositor:
    def __init__(self, capas: Sequence[BaseLayer], salida: Tuple[int, int],
                 color_fondo: Tuple[int, int, int] = (0, 0, 0)):
        self.capas = list(capas)
        self.salida = salida
        self.color_fondo = color_fondo

    def componer(self, ctx: ContextoFrame) -> Image.Image:
        base = Image.new("RGBA", self.salida, (*self.color_fondo, 255))
        ancho, alto = self.salida
        for capa in self.capas:
            res = capa.renderizar(ctx)
            if res is None:
                continue
            for parte in ((res,) if isinstance(res, CapaRGBA) else res):     # una capa puede aportar varias imágenes
                img, x, y = parte.imagen, parte.x, parte.y
                # Recorte a la zona visible (alpha_composite no admite destinos fuera del lienzo)
                x0, y0 = max(x, 0), max(y, 0)
                x1, y1 = min(x + img.width, ancho), min(y + img.height, alto)
                if x1 <= x0 or y1 <= y0:
                    continue
                visible = img.crop((x0 - x, y0 - y, x1 - x, y1 - y))
                base.alpha_composite(visible, dest=(x0, y0))
        return base.convert("RGB")
