"""Alineación del parpadeo por la montura de las gafas.

Una imagen de parpadeo generada por IA es una redibujada de todo el personaje: rara vez coincide al píxel con la pose (contorno, pelo,
cejas). Alinearla por la silueta de la cabeza falla unos píxeles, y esos píxeles se ven como un salto. La montura azul oscuro de las
gafas sí es un detalle nítido y estable, así que:

  * el parche se recorta solo del INTERIOR de las gafas: sus bordes caen por el centro del marco oscuro, donde pose e imagen de
    parpadeo son igual de oscuras y el corte no se ve; las cejas ni se tocan;
  * la imagen se desplaza lo justo para que su montura caiga sobre la de la pose."""
from typing import Optional, Sequence, Tuple

import numpy as np
from PIL import Image

RADIO_BUSQUEDA = 14                  # píxeles que puede moverse la imagen de parpadeo hasta encajar
MARGEN_BUSQUEDA = 8                  # alrededor de la caja vieja donde se busca la montura


def mascara_montura(img: Image.Image) -> np.ndarray:
    """Píxeles del marco de las gafas: azul oscuro y opaco (no el iris, que es azul claro, ni las cejas, el pelo o la piel)."""
    a = np.asarray(img.convert("RGBA")).astype(int)
    r, g, b, alfa = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    return (alfa > 128) & (b - r >= 20) & (b - g >= 8) & ((r + g + b) / 3 < 100)


def _barra(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> float:
    """Grosor típico del marco: largo de los tramos verticales de marco que arrancan en el borde superior."""
    tramos = []
    for x in range(x0, x1 + 1, max(1, (x1 - x0) // 12)):
        col = mask[y0:y1 + 1, x]
        if col.any():
            inicio = int(np.argmax(col))
            largo = 0
            while inicio + largo < len(col) and col[inicio + largo]:
                largo += 1
            tramos.append(largo)
    return float(np.median(tramos)) if tramos else 4.0


def caja_de_montura(pose: Image.Image, caja_vieja: Sequence[float]) -> Optional[Tuple[int, int, int, int]]:
    """Caja (x, y, ancho, alto) = el rectángulo exterior de la montura dentro de la caja vieja, encogido medio grosor del marco por
    cada lado para que sus bordes pasen por el centro del marco. None si no hay montura (otra imagen, otra pose sin gafas)."""
    bx, by, bw, bh = (int(round(float(v))) for v in caja_vieja)
    m = mascara_montura(pose)
    X0, Y0 = max(0, bx - MARGEN_BUSQUEDA), max(0, by - MARGEN_BUSQUEDA)
    X1, Y1 = min(m.shape[1], bx + bw + MARGEN_BUSQUEDA), min(m.shape[0], by + bh + MARGEN_BUSQUEDA)
    zona = m[Y0:Y1, X0:X1]
    if zona.sum() < 40:
        return None
    ys, xs = np.where(zona)
    x0, x1 = int(np.percentile(xs, 0.3)) + X0, int(np.percentile(xs, 99.7)) + X0
    y0, y1 = int(np.percentile(ys, 0.3)) + Y0, int(np.percentile(ys, 99.7)) + Y0
    t = _barra(m, x0, y0, x1, y1)
    inset = t / 2
    return (round(x0 + inset), round(y0 + inset), max(1, round(x1 - x0 + 1 - t)), max(1, round(y1 - y0 + 1 - t)))


def desplazamiento_por_montura(pose: Image.Image, parpadeo: Image.Image, caja: Sequence[float],
                               radio: int = RADIO_BUSQUEDA) -> Tuple[int, int]:
    """Cuánto hay que mover (dx, dy) la imagen de parpadeo para que su montura caiga sobre la de la pose: el desplazamiento que
    maximiza el solape (IoU) entre las dos máscaras de montura cerca de la caja. Las dos imágenes comparten lienzo."""
    bx, by, bw, bh = (int(round(float(v))) for v in caja)
    pad = radio + MARGEN_BUSQUEDA
    X0, Y0 = max(0, bx - pad), max(0, by - pad)
    X1, Y1 = bx + bw + pad, by + bh + pad
    mp = mascara_montura(pose)[Y0:Y1, X0:X1]
    mb = mascara_montura(parpadeo)[Y0:Y1, X0:X1]
    alto, ancho = mp.shape
    mejor, mejor_s = (0, 0), -1.0
    for dy in range(-radio, radio + 1):
        for dx in range(-radio, radio + 1):
            ys0, ys1, xs0, xs1 = max(0, dy), min(alto, alto + dy), max(0, dx), min(ancho, ancho + dx)
            a = mp[ys0:ys1, xs0:xs1]
            b = mb[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            union = int((a | b).sum())
            s = (int((a & b).sum()) / union) if union else 0.0
            if s > mejor_s + 1e-9 or (abs(s - mejor_s) <= 1e-9 and abs(dx) + abs(dy) < abs(mejor[0]) + abs(mejor[1])):
                mejor, mejor_s = (dx, dy), s
    return mejor
