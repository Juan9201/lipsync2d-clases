"""FR-040, FR-041, FR-042: parpadeos, respiración y movimiento leve reproducibles con semilla."""
import numpy as np
import pytest

from src.animation import (calcular_hablando, generar_animacion, generar_parpadeos)
from src.timeline import Visema

FPS = 25
N = 7500            # una clase de 5 minutos


# ---------------- FR-040: parpadeos ----------------
def test_los_intervalos_y_duraciones_cumplen_el_rango():
    parpadeos = generar_parpadeos(N, FPS, semilla=11)
    assert 40 <= len(parpadeos) <= 150
    for p in parpadeos:
        assert 3 <= p.frames <= 5
        assert p.f0 + p.frames <= N
    for a, b in zip(parpadeos, parpadeos[1:]):
        assert 2 * FPS <= b.f0 - a.f0 <= 6 * FPS, (a, b)
    assert 2 * FPS <= parpadeos[0].f0 <= 6 * FPS


def test_misma_semilla_mismos_parpadeos_y_otra_semilla_distintos():
    assert generar_parpadeos(N, FPS, 5) == generar_parpadeos(N, FPS, 5)
    assert generar_parpadeos(N, FPS, 5) != generar_parpadeos(N, FPS, 6)


def test_un_video_corto_puede_no_tener_parpadeos_y_no_falla():
    assert generar_parpadeos(30, FPS, 1) == []


# ---------------- FR-042: hablando ----------------
def test_pausas_cortas_no_cortan_el_habla_pero_las_largas_si():
    visemas = [Visema(0, 30, "X"), Visema(30, 100, "B"), Visema(100, 105, "X"),   # pausa de 5 frames
               Visema(105, 200, "D"), Visema(200, 400, "X"), Visema(400, 450, "C")]
    h = calcular_hablando(visemas, 450)
    assert h == [[30, 200], [400, 450]]


def test_sin_voz_no_hay_habla():
    assert calcular_hablando([Visema(0, 100, "X")], 100) == []


# ---------------- FR-041: respiración ----------------
def test_la_respiracion_queda_dentro_de_mas_menos_medio_por_ciento_y_es_continua():
    a = generar_animacion(N, FPS, 3, hablando=[], amp_respiracion=0.005, amp_cabeza_px=6)
    assert np.all(np.abs(a.escala - 1) <= 0.005 + 1e-12)
    assert np.abs(np.diff(a.escala)).max() <= 0.005 * 2 * np.pi / (4.0 * FPS) * 1.01
    assert a.escala.max() > 1.004 and a.escala.min() < 0.996            # la onda sí oscila


def test_respiracion_cero_deja_la_escala_en_uno():
    a = generar_animacion(N, FPS, 3, hablando=[[0, N]], amp_respiracion=0.0, amp_cabeza_px=0)
    assert np.all(a.escala == 1.0) and np.all(a.dx == 0) and np.all(a.dy == 0)


# ---------------- FR-042: movimiento leve ----------------
def test_solo_hay_movimiento_mientras_se_habla():
    a = generar_animacion(1000, FPS, 4, hablando=[[300, 600]], amp_respiracion=0.005, amp_cabeza_px=6)
    assert np.all(a.dx[:280] == 0) and np.all(a.dy[:280] == 0)          # antes de hablar (con rampa de entrada)
    assert np.all(a.dx[620:] == 0) and np.all(a.dy[620:] == 0)          # después (con rampa de salida)
    assert np.abs(a.dx[300:600]).max() > 1.0                            # sí se mueve al hablar


def test_el_movimiento_es_suave_sin_saltos_entre_frames_consecutivos():
    a = generar_animacion(N, FPS, 9, hablando=[[100, 3000], [3200, 7000]], amp_respiracion=0.005, amp_cabeza_px=6)
    assert np.abs(np.diff(a.dx)).max() <= 0.35 * 6
    assert np.abs(np.diff(a.dy)).max() <= 0.35 * 6
    assert np.abs(a.dx).max() <= 6 + 1e-9 and np.abs(a.dy).max() <= 6 + 1e-9


def test_misma_semilla_misma_animacion():
    uno = generar_animacion(2000, FPS, 8, [[0, 2000]], 0.005, 6)
    dos = generar_animacion(2000, FPS, 8, [[0, 2000]], 0.005, 6)
    otra = generar_animacion(2000, FPS, 9, [[0, 2000]], 0.005, 6)
    assert np.array_equal(uno.dx, dos.dx) and np.array_equal(uno.escala, dos.escala)
    assert not np.array_equal(uno.dx, otra.dx)
