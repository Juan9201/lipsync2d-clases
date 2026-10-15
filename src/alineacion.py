"""Alineación de cabezas en el cambio de pose (FR-059).

Cada pose la dibujó la IA con la cabeza en un sitio ligeramente distinto (hasta 140 px en un lienzo
de 3840): sin corregirlo, la cabeza «salta» en cada corte. Aquí se mide dónde está la cabeza de cada
pose y cuánto hay que moverla para dejarla donde está la de la pose de referencia.

La cabeza se mide por el centro de su silueta en la franja superior de la figura (el pelo): un brazo
levantado o un libro no la desplazan, porque quedan mucho más abajo."""
from typing import Tuple

import numpy as np
from PIL import Image

from src.errores import AssetInvalido

BANDA_CABEZA = 0.12        # alto de la franja de medición, como fracción del alto de la imagen
UMBRAL_ALFA = 200


def centro_cabeza(img: Image.Image) -> Tuple[float, float]:
    """Centro (x, y) de la silueta de la cabeza, en píxeles de la imagen."""
    alfa = np.asarray(img.convert("RGBA"))[:, :, 3] > UMBRAL_ALFA
    filas = np.where(alfa.any(axis=1))[0]
    if len(filas) == 0:
        raise AssetInvalido("No se encontró la cabeza: la imagen de la pose está vacía (todo transparente)",
                            "Revisa que cuerpo.png tenga al personaje con fondo transparente")
    y0 = int(filas[0])
    y1 = y0 + max(1, int(BANDA_CABEZA * img.height))
    ys, xs = np.where(alfa[y0:y1])
    return float(xs.mean()), float(ys.mean() + y0)


def desplazamiento_alineacion(pelo: Tuple[float, float], referencia: Tuple[float, float]) -> Tuple[float, float]:
    """Cuánto mover una pose (en píxeles del lienzo) para que su cabeza coincida con la de referencia."""
    return referencia[0] - pelo[0], referencia[1] - pelo[1]
