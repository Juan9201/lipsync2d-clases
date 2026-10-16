"""T071 de punta a punta (FR-044, FR-053, FR-090): un render real dirigido. Se mide sobre el MP4: la cámara cambia de
plano entre tomas (la cabeza cambia de tamaño), al cambiar de pose se mezclan 2 frames y no hay saltos raros."""
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from src import rutas
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.validacion import VISEMAS
from src.render import ParametrosRender, renderizar

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (rutas.FFMPEG.exists() and rutas.RHUBARB.exists() and EJEMPLO.exists()),
                                 reason="faltan ffmpeg, Rhubarb o el audio de ejemplo")]

LIENZO = (640, 360)
SALIDA = (640, 360)
PIEL = (230, 180, 150)
ROJO, AZUL = (255, 0, 0), (0, 0, 255)


def _pose(raiz, nombre, cuerpo):
    carpeta = raiz / "personajes" / "profe" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    cx, cy = 320, 140
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((cx - 80, cy + 50, cx + 80, LIENZO[1]), fill=(*cuerpo, 255))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(*PIEL, 255))
    im.save(carpeta / "cuerpo.png")
    for i, v in enumerate(VISEMAS):
        Image.new("RGBA", (50 + 4 * i, 20 + 2 * i), (200, 20, 20, 255)).save(carpeta / "bocas" / f"{v}.png")
    formas = {v: {"x": cx, "y": cy + 30, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), LIENZO, formas)


@pytest.fixture
def clase(proyecto_tmp):
    _pose(proyecto_tmp, "frontal_neutro_01", ROJO)
    _pose(proyecto_tmp, "frontal_explicar_01", AZUL)
    esc = proyecto_tmp / "escenarios" / "E1_calle" / "fondo.png"
    esc.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), (60, 90, 140)).save(esc)
    audio = proyecto_tmp / "clases" / "clase 01.mp3"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-t", "30", "-i", str(EJEMPLO), "-c", "copy", str(audio)], check=True)
    reglas = proyecto_tmp / "reglas.yaml"
    reglas.write_text(yaml.safe_dump({"toma_s": [3, 4], "acentos": {"activo": False},
                                      "planos": {"permitidos": ["PL2", "PL4"], "inicial": "PL2"},
                                      "cambio": {"prob_plano": 0.5}}), encoding="utf-8")
    return proyecto_tmp, audio, reglas


def _frames(video):
    r = subprocess.run([str(rutas.FFMPEG), "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, SALIDA[1], SALIDA[0], 3).astype(int)


def _alto_de_cabeza(frames):
    """Alto en píxeles de la cabeza (de la fila más alta a la más baja con piel) en cada frame: no depende de la boca."""
    mascara = np.abs(frames - np.array(PIEL)).max(3) <= 14
    filas = mascara.any(2)
    return np.array([np.ptp(np.where(f)[0]) if f.any() else 0 for f in filas])


def _render(clase, **kw):
    raiz, audio, reglas = clase
    base = dict(personaje="profe", audio=audio, resolucion=SALIDA, semilla=2, escenario="E1",
                poses=["frontal_neutro_01", "frontal_explicar_01"], director=True, reglas=reglas)
    base.update(kw)
    return renderizar(ParametrosRender(**base), raiz=raiz)


def test_el_director_cambia_el_plano_de_la_camara_durante_la_clase(clase):
    frames = _frames(_render(clase))
    alto = _alto_de_cabeza(frames)
    assert alto.max() > 1.3 * alto.min() > 0                                   # hubo planos abiertos y cerrados
    saltos = np.abs(np.diff(alto))
    assert (saltos > 0.3 * alto.max()).sum() >= 1                                # y al menos un corte de cámara


def test_al_cambiar_de_pose_hay_frames_mezclados_y_nunca_mas_de_dos_seguidos(clase):
    frames = _frames(_render(clase))
    cuerpo = frames[:, SALIDA[1] - 6, SALIDA[0] // 2]                           # color del torso en la parte baja
    rojo = np.abs(cuerpo - np.array(ROJO)).max(1) <= 40
    azul = np.abs(cuerpo - np.array(AZUL)).max(1) <= 40
    mezclado = ~(rojo | azul)
    assert mezclado.sum() >= 2, "no se vio ninguna mezcla entre poses"
    racha = 0
    for m in mezclado:
        racha = racha + 1 if m else 0
        assert racha <= 2
    assert rojo.any() and azul.any()                                           # las dos poses se usaron


def test_sin_director_el_plano_queda_fijo(clase):
    frames = _frames(_render(clase, director=False, poses=["frontal_neutro_01"], plano="PL4"))
    alto = _alto_de_cabeza(frames)
    assert alto.max() - alto.min() <= 3                                        # la cabeza no cambia de tamaño


def test_el_log_cuenta_las_decisiones_del_director(clase):
    raiz, _, _ = clase
    _render(clase)
    log = next((raiz / "logs").glob("*.log")).read_text(encoding="utf-8")
    assert "Director:" in log and "cambio de cámara" in log or "reposo" in log
