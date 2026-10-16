"""Animación secundaria (US3): parpadeos (FR-040), respiración (FR-041) y movimiento leve al
hablar (FR-042). Todo es una función pura de (frame, semilla): misma semilla, mismo resultado."""
from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from src.timeline import Parpadeo, Visema

PERIODO_RESPIRACION_S = 4.0       # una respiración completa cada 4 s
RAMPA_FRAMES = 11                 # entrada y salida suave del movimiento (ventana de promedio)
PAUSA_QUE_NO_CORTA_FRAMES = 12    # una pausa de hasta ~0,5 s no detiene el movimiento


@dataclass(frozen=True)
class Animacion:
    escala: np.ndarray   # factor de respiración por frame (1 ± amplitud)
    dx: np.ndarray       # desplazamiento horizontal por frame, en píxeles del lienzo
    dy: np.ndarray       # desplazamiento vertical por frame, en píxeles del lienzo


def _rng(semilla: int, flujo: int) -> np.random.Generator:
    return np.random.default_rng([int(semilla), flujo])


PROB_DOBLE = 0.10                 # FR-043: probabilidad de que un parpadeo sea doble


def _libre_de_cortes(f0: int, span: int, cortes: Sequence[int]) -> bool:
    return not any(f0 <= c < f0 + span for c in cortes)


def generar_parpadeos(n_frames: int, fps: int, semilla: int, prob_doble: float = PROB_DOBLE,
                      cortes: Sequence[int] = ()) -> List[Parpadeo]:
    """Intervalos aleatorios de 2 a 6 s entre inicios; cada parpadeo dura 3 a 5 frames y, con la probabilidad
    `prob_doble`, es doble (FR-043). Ningún parpadeo ocupa el frame de un cambio de pose (`cortes`): si le toca, se
    corre dentro del intervalo permitido al frame libre más cercano."""
    rng, rng_doble = _rng(semilla, 1), _rng(semilla, 3)
    minimo, maximo = 2 * fps, 6 * fps
    cortes = sorted(c for c in cortes if c > 0)
    parpadeos: List[Parpadeo] = []
    previo = None
    f0 = int(rng.integers(minimo, maximo + 1))
    while True:
        duracion = int(rng.integers(3, 6))
        doble = bool(rng_doble.random() < prob_doble)
        parp = Parpadeo(f0, duracion, doble)
        if previo is None:
            lo, hi = minimo, maximo
        else:
            lo, hi = previo + minimo, previo + maximo
        if not _libre_de_cortes(f0, parp.span, cortes):
            # frame libre más cercano que siga cumpliendo el intervalo (si los cortes son tan seguidos que no hay,
            # se prefiere respetar el intervalo y se deja el parpadeo donde cayó)
            for d in range(1, hi - lo + 1):
                for cand in (f0 + d, f0 - d):
                    if lo <= cand <= hi and _libre_de_cortes(cand, parp.span, cortes):
                        parp = Parpadeo(cand, duracion, doble)
                        break
                else:
                    continue
                break
        if parp.f0 + parp.span > n_frames:
            break
        parpadeos.append(parp)
        previo = parp.f0
        f0 = parp.f0 + int(rng.integers(minimo, maximo + 1))
    return parpadeos


def calcular_hablando(visemas: Sequence[Visema], n_frames: int,
                      pausa_max: int = PAUSA_QUE_NO_CORTA_FRAMES) -> List[List[int]]:
    """Tramos [f0, f1) con voz. Las pausas cortas no los parten, para que el personaje no
    arranque y pare a cada respiro."""
    tramos: List[List[int]] = []
    for v in visemas:
        if v.v == "X":
            continue
        if tramos and v.f0 - tramos[-1][1] <= pausa_max:
            tramos[-1][1] = v.f1
        else:
            tramos.append([v.f0, v.f1])
    return tramos


def generar_animacion(n_frames: int, fps: int, semilla: int, hablando: Sequence[Sequence[int]],
                      amp_respiracion: float, amp_cabeza_px: float) -> Animacion:
    rng = _rng(semilla, 2)
    fase = rng.uniform(0, 2 * np.pi, 5)
    t = np.arange(n_frames) / fps

    escala = 1.0 + amp_respiracion * np.sin(2 * np.pi * t / PERIODO_RESPIRACION_S + fase[0])

    mascara = np.zeros(n_frames)
    for f0, f1 in hablando:
        mascara[f0:f1] = 1.0
    envolvente = np.convolve(mascara, np.ones(RAMPA_FRAMES) / RAMPA_FRAMES, mode="same")

    onda_x = 0.6 * np.sin(2 * np.pi * 0.37 * t + fase[1]) + 0.4 * np.sin(2 * np.pi * 0.71 * t + fase[2])
    onda_y = 0.6 * np.sin(2 * np.pi * 0.31 * t + fase[3]) + 0.4 * np.sin(2 * np.pi * 0.53 * t + fase[4])
    dx = amp_cabeza_px * envolvente * onda_x
    dy = 0.5 * amp_cabeza_px * envolvente * onda_y
    return Animacion(escala, dx, dy)
