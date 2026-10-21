"""Iluminación del personaje a partir de las luces de la escena. Los mapas (un multiplicador de color y un reborde aditivo por píxel)
dependen de la silueta, de la posición y de las luces, no de la boca ni de los ojos: se calculan una vez por pose y plano, y cada
frame solo aplica unas pocas operaciones. Nada de esto mueve píxeles: la boca y los ojos siguen donde estaban."""
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageFilter


def mapas_de_luz(personaje: Image.Image, luces: Sequence[dict], ambiente: Sequence[float], y_borde: float,
                 rampa: float, suavidad: float) -> Tuple[np.ndarray, np.ndarray]:
    """`luces` ya en píxeles de `personaje`. Devuelve (multiplicador H×W×3, reborde H×W×3)."""
    w, h = personaje.size
    arr = np.asarray(personaje, dtype=np.float32) / 255.0
    alfa = arr[..., 3]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # relieve falso: la silueta suavizada hace de «volumen»; su gradiente da la orientación del contorno
    masc = Image.fromarray((alfa * 255).astype(np.uint8))
    altura = np.asarray(masc.filter(ImageFilter.GaussianBlur(max(suavidad, 0.5))), dtype=np.float32) / 255.0
    gy, gx = np.gradient(altura)
    n = np.stack([-gx * 14, -gy * 14, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    luz_total = np.zeros((h, w, 3), np.float32) + np.asarray(ambiente, np.float32)
    mira = np.zeros((h, w), np.float32)
    for L in luces:
        lx, ly = L["pos"]
        v = np.stack([lx - xx, ly - yy, np.full_like(xx, L["altura"])], -1)
        dist = np.linalg.norm(v, axis=-1, keepdims=True)
        dirv = v / np.maximum(dist, 1e-3)
        difusa = np.clip((n * dirv).sum(-1, keepdims=True), 0, 1)
        caida = np.exp(-(dist[..., 0] ** 2) / (2 * L["alcance"] ** 2))[..., None]
        luz_total += np.array(L["color"], np.float32) * L["fuerza"] * caida * (0.25 + 0.75 * difusa)
        plano = np.stack([lx - xx, ly - yy], -1)
        plano /= np.maximum(np.linalg.norm(plano, axis=-1, keepdims=True), 1e-3)
        mira += (plano * n[..., :2]).sum(-1) * L["fuerza"] * np.exp(-((xx - lx) ** 2 + (yy - ly) ** 2) / (2 * (L["alcance"] * 1.2) ** 2))
    # oclusión de la mesa: lo que está cerca del borde de la mesa recibe menos luz
    oclusion = 1 - 0.42 * np.clip((yy - (y_borde - rampa)) / max(rampa, 1.0), 0, 1)
    luz_total *= oclusion[..., None]
    # la luz cambia sobre todo el brillo; su color se aplica a medias para que la piel y la ropa no se ensucien
    brillo = (luz_total * np.array([0.30, 0.59, 0.11], np.float32)).sum(-1, keepdims=True)
    tinte = luz_total / np.maximum(brillo, 1e-4)
    mult = brillo * (1 + 0.65 * (tinte - 1))
    # reborde cálido del lado de las lámparas
    borde = np.asarray(masc.filter(ImageFilter.GaussianBlur(max(suavidad * 0.2, 0.5))), dtype=np.float32) / 255.0
    interior = np.asarray(masc.filter(ImageFilter.GaussianBlur(max(suavidad * 0.045, 0.3))), dtype=np.float32) / 255.0
    contorno = np.clip(interior - borde, 0, 1) * 3.5 * (alfa > 0.5)
    suma = np.array([1.0, 0.82, 0.58], np.float32) * (contorno * np.clip(np.clip(mira, 0, None), 0, 1.2) * 0.38)[..., None]
    return mult.astype(np.float32), suma.astype(np.float32)


def aplicar_luz(personaje: Image.Image, mult: np.ndarray, suma: np.ndarray) -> Image.Image:
    """Aplica los mapas a un frame del personaje (RGBA); el canal alfa no cambia."""
    arr = np.asarray(personaje, dtype=np.float32) / 255.0
    lit = arr[..., :3] * mult
    lit = lit / (1 + 0.30 * lit)                                        # compresión suave: el blanco no se quema
    lit = np.clip(lit * 1.22 + suma, 0, 1)
    return Image.fromarray((np.dstack([lit, arr[..., 3]]) * 255).astype(np.uint8), "RGBA")
