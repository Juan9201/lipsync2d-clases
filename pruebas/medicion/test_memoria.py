"""NFR-001: el pico de RAM < 2 GB y no crece con la duración (audios de 1 y 10 minutos).
NFR-002: un audio de 5 minutos se renderiza en <= 10 minutos.

Usa tus assets reales (pose P1 y escenario E1 del proyecto). Se ejecuta con:
    pytest -m "lento and medicion" -s
"""
import sys

import pytest

from pruebas.medicion.utilidades import medir_proceso
from pruebas.utiles import EJEMPLO, FFMPEG, RAIZ, concatenar, recortar_audio

pytestmark = [pytest.mark.lento, pytest.mark.medicion,
              pytest.mark.skipif(not (FFMPEG.exists() and EJEMPLO.exists()
                                      and (RAIZ / "personajes" / "profesor" / "poses").exists()
                                      and (RAIZ / "escenarios" / "E1_salon" / "fondo.png").exists()),
                                 reason="faltan los assets reales (pose P1 y escenario E1)")]

GB = 1024 ** 3


def _render(audio):
    cmd = [sys.executable, "-m", "src.render", "--personaje", "profesor", "--pose", "P1", "--escenario", "E1",
           "--audio", str(audio)]
    codigo, seg, pico = medir_proceso(cmd, RAIZ)
    for f in (RAIZ / "salidas").glob(f"{audio.stem}_*.mp4"):
        f.unlink()
    (RAIZ / "logs" / f"{audio.stem}.log").unlink(missing_ok=True)
    assert codigo == 0, "el render falló"
    return seg, pico


def test_ram_con_1_y_10_minutos(tmp_path):
    uno = recortar_audio(EJEMPLO, tmp_path / "medicion_1min.mp3", 60)
    diez = concatenar([EJEMPLO] * 3 + [recortar_audio(EJEMPLO, tmp_path / "resto.mp3", 40)],
                      tmp_path / "medicion_10min.mp3")
    s1, p1 = _render(uno)
    s10, p10 = _render(diez)
    print(f"\n1 min : {s1:6.1f} s, pico {p1 / 2**20:5.0f} MB\n10 min: {s10:6.1f} s, pico {p10 / 2**20:5.0f} MB")
    assert p1 < 2 * GB and p10 < 2 * GB
    assert p10 <= p1 * 1.5, "la RAM crece con la duración del audio"


def test_clase_de_5_minutos_en_menos_de_10_minutos(tmp_path):
    cinco = recortar_audio(EJEMPLO, tmp_path / "medicion_5min.mp3", 300)
    seg, pico = _render(cinco)
    print(f"\n5 min : {seg:6.1f} s, pico {pico / 2**20:5.0f} MB")
    assert seg <= 600
