"""T092 + T096 + T098 de punta a punta (FR-057, FR-059, FR-062, FR-067): un render real con varias poses
calibradas por forma, fondo en video y alineación de cabezas, medido sobre el MP4 resultante."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src import rutas
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.validacion import VISEMAS
from src.errores import AssetInvalido
from src.render import ParametrosRender, renderizar

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (rutas.FFMPEG.exists() and rutas.RHUBARB.exists() and EJEMPLO.exists()),
                                 reason="faltan ffmpeg, Rhubarb o el audio de ejemplo")]

LIENZO = (640, 360)
SALIDA = (640, 360)
PIEL = (230, 180, 150)


def _pose(raiz, nombre, cabeza):
    carpeta = raiz / "personajes" / "profe" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = cabeza
    d.rectangle((cx - 80, cy + 50, cx + 80, LIENZO[1]), fill=(245, 245, 245, 255))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(*PIEL, 255))
    im.save(carpeta / "cuerpo.png")
    for i, v in enumerate(VISEMAS):
        Image.new("RGBA", (50 + 4 * i, 20 + 2 * i), (200, 20, 20, 255)).save(carpeta / "bocas" / f"{v}.png")
    formas = {v: {"x": cx, "y": cy + 30, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), LIENZO, formas)
    return carpeta


@pytest.fixture
def clase(proyecto_tmp):
    _pose(proyecto_tmp, "frontal_neutro_01", (320, 120))
    _pose(proyecto_tmp, "frontal_explicar_01", (380, 160))        # cabeza 60 px a la derecha y 40 abajo
    esc = proyecto_tmp / "escenarios" / "E1_calle" / "fondo.mp4"
    esc.parent.mkdir(parents=True)
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=640x360:rate=25:duration=4", "-pix_fmt", "yuv420p", str(esc)], check=True)
    audio = proyecto_tmp / "clases" / "clase 01.mp3"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-t", "10", "-i", str(EJEMPLO), "-c", "copy", str(audio)],
                   check=True)
    return proyecto_tmp, audio


def _frame(ruta, segundo):
    r = subprocess.run([str(rutas.FFMPEG), "-v", "error", "-ss", str(segundo), "-i", str(ruta), "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(SALIDA[1], SALIDA[0], 3).astype(int)


def _centro_piel(frame):
    m = np.abs(frame - np.array(PIEL)).max(2) <= 14                 # tolerancia por la compresión H.264
    ys, xs = np.where(m)
    assert len(xs) > 500
    return xs.mean(), ys.mean()


def _sonda(ruta):
    out = subprocess.run([str(rutas.FFPROBE), "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
                          str(ruta)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _render(clase, **kw):
    raiz, audio = clase
    base = dict(personaje="profe", audio=audio, resolucion=SALIDA, semilla=3, escenario="E1",
                poses=["frontal_neutro_01", "frontal_explicar_01"], duracion_toma_s=5.0)
    base.update(kw)
    return renderizar(ParametrosRender(**base), raiz=raiz)


def test_render_con_dos_poses_y_fondo_en_video_produce_un_mp4_valido(clase):
    final = _render(clase)
    datos = _sonda(final)
    video = next(s for s in datos["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264" and video["r_frame_rate"] == "25/1"
    assert abs(float(datos["format"]["duration"]) - 10.0) < 0.2
    assert not list(final.parent.glob("*.part.mp4"))


def test_el_fondo_se_mueve_durante_la_clase(clase):
    final = _render(clase)
    a, b, a2 = _frame(final, 1.0), _frame(final, 2.0), _frame(final, 1.0)
    izquierda = (slice(0, SALIDA[1]), slice(0, 200))                 # franja sin personaje
    assert np.abs(a[izquierda] - a2[izquierda]).mean() == 0          # el mismo instante es idéntico
    assert np.abs(a[izquierda] - b[izquierda]).mean() > 3            # y entre dos instantes el fondo cambia


def test_con_alineacion_la_cabeza_no_salta_al_cambiar_de_pose(clase):
    final = _render(clase)                                           # el corte cae hacia los 5 s
    antes, despues = _centro_piel(_frame(final, 1.0)), _centro_piel(_frame(final, 9.0))
    assert abs(despues[0] - antes[0]) < 3 and abs(despues[1] - antes[1]) < 3


def test_sin_alineacion_la_cabeza_queda_donde_se_dibujo(clase):
    final = _render(clase, alinear=False)
    antes, despues = _centro_piel(_frame(final, 1.0)), _centro_piel(_frame(final, 9.0))
    assert despues[0] - antes[0] == pytest.approx(60, abs=4) and despues[1] - antes[1] == pytest.approx(40, abs=4)


def test_una_pose_inexistente_lista_las_disponibles(clase):
    with pytest.raises(AssetInvalido) as exc:
        _render(clase, poses=["frontal_neutro_01", "frontal_no_existe_09"])
    assert "frontal_no_existe_09" in str(exc.value) and "frontal_explicar_01" in str(exc.value)


def test_una_sola_pose_v3_se_renderiza_sin_poses_ciclicas(clase):
    final = _render(clase, poses=None, pose="frontal_neutro_01")
    assert final.exists()


def test_el_plano_busto_acerca_a_la_cabeza(clase):
    lejos = _render(clase, plano="PL1", poses=["frontal_neutro_01"])
    lejos_a = _frame(lejos, 2.0)
    cerca = _render(clase, plano="PL4", poses=["frontal_neutro_01"], clase_id="cerca")
    cerca_a = _frame(cerca, 2.0)
    n_lejos = (np.abs(lejos_a - np.array(PIEL)).max(2) <= 14).sum()
    n_cerca = (np.abs(cerca_a - np.array(PIEL)).max(2) <= 14).sum()
    assert n_cerca > 2 * n_lejos                                     # la cabeza ocupa mucho más con el plano cerrado
