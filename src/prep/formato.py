"""Ajuste a 16:9 sin deformar al personaje, y avisos de resolución (FR-085)."""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps

RATIO = 16 / 9


@dataclass(frozen=True)
class ResultadoFormato:
    imagen: Image.Image
    avisos: List[str] = field(default_factory=list)
    modificada: bool = False


def es_16_9(ancho: int, alto: int) -> bool:
    return abs(ancho / alto - RATIO) <= 0.01 * RATIO


def ajustar_16_9(im: Image.Image, modo: str = "recortar", foco_x: Optional[int] = None,
                 salida: Tuple[int, int] = (1280, 720)) -> ResultadoFormato:
    """`modo`: "recortar" (quita bordes, centrado o en torno a `foco_x`) o "rellenar" (añade
    bandas con el fondo difuminado). Nunca cambia las proporciones de la imagen original."""
    if modo not in ("recortar", "rellenar"):
        raise ValueError("modo debe ser «recortar» o «rellenar»")
    avisos: List[str] = []
    w, h = im.size
    modificada = False
    if not es_16_9(w, h):
        accion = "se recorta" if modo == "recortar" else "se rellena con el fondo difuminado"
        avisos.append(f"La imagen mide {w}x{h} y no es 16:9; {accion} sin deformar al personaje")
        modificada = True
        if modo == "recortar":
            if w / h > RATIO:
                nuevo_w = round(h * RATIO)
                centro = foco_x if foco_x is not None else w // 2
                x0 = min(max(centro - nuevo_w // 2, 0), w - nuevo_w)
                im = im.crop((x0, 0, x0 + nuevo_w, h))
            else:
                nuevo_h = round(w / RATIO)
                y0 = (h - nuevo_h) // 2
                im = im.crop((0, y0, w, y0 + nuevo_h))
        else:
            lienzo = (w, math.ceil(w / RATIO)) if w / h > RATIO else (math.ceil(h * RATIO), h)
            fondo = ImageOps.fit(im.convert("RGB"), lienzo).filter(
                ImageFilter.GaussianBlur(max(lienzo) // 40))
            fondo.paste(im.convert("RGB"), ((lienzo[0] - w) // 2, (lienzo[1] - h) // 2))
            im = fondo
    if im.width < salida[0] or im.height < salida[1]:
        avisos.append(f"La imagen ({im.width}x{im.height}) es menor que la salida "
                      f"{salida[0]}x{salida[1]}; se ampliará y puede verse borrosa")
    return ResultadoFormato(im, avisos, modificada)
