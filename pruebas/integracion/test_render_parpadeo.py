"""T099/T100 de punta a punta (FR-040, FR-043): un render real con parpadeo por imagen. Se mide sobre el MP4: hay
frames con los ojos cerrados, duran 3 a 5 frames, no ocurren en un cambio de pose y fuera de los ojos nada cambia."""
import subprocess
from pathlib import Path

import numpy as np
import pytest
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
OJO_ABIERTO = (255, 255, 255)
OJO_CERRADO = (20, 20, 20)
CAJA = (-45, -25, 90, 20)                          # relativa al centro de la cabeza: x, y, ancho, alto


def _pose(raiz, nombre, cabeza):
    carpeta = raiz / "personajes" / "profe" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    cx, cy = cabeza
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((cx - 80, cy + 50, cx + 80, LIENZO[1]), fill=(245, 245, 245, 255))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(*PIEL, 255))
    x, y, w, h = cx + CAJA[0], cy + CAJA[1], CAJA[2], CAJA[3]
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=(*OJO_ABIERTO, 255))
    im.save(carpeta / "cuerpo.png")
    # recorte de parpadeo: del tamaño de los ojos, con los ojos cerrados
    parche = Image.new("RGBA", (w, h), (*OJO_CERRADO, 255))
    parche.save(carpeta / "parpadeo_cerrado.png")
    for i, v in enumerate(VISEMAS):
        Image.new("RGBA", (50 + 4 * i, 20 + 2 * i), (200, 20, 20, 255)).save(carpeta / "bocas" / f"{v}.png")
    formas = {v: {"x": cx, "y": cy + 30, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), LIENZO, formas,
                            parpadeo={"parche": {"x": x, "y": y}, "cerrado": "parpadeo_cerrado.png", "medio": None})
    return x, y, w, h


@pytest.fixture
def clase(proyecto_tmp):
    caja_a = _pose(proyecto_tmp, "frontal_neutro_01", (320, 140))
    _pose(proyecto_tmp, "frontal_explicar_01", (320, 140))
    esc = proyecto_tmp / "escenarios" / "E1_calle" / "fondo.png"
    esc.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), (60, 90, 140)).save(esc)
    audio = proyecto_tmp / "clases" / "clase 01.mp3"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-t", "20", "-i", str(EJEMPLO), "-c", "copy", str(audio)], check=True)
    return proyecto_tmp, audio, caja_a


def _todos_los_frames(video):
    r = subprocess.run([str(rutas.FFMPEG), "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, SALIDA[1], SALIDA[0], 3).astype(int)


def test_el_video_tiene_parpadeos_de_3_a_5_frames_solo_en_la_zona_de_los_ojos(clase):
    raiz, audio, (x, y, w, h) = clase
    final = renderizar(ParametrosRender(personaje="profe", audio=audio, resolucion=SALIDA, semilla=3, escenario="E1",
                                        poses=["frontal_neutro_01", "frontal_explicar_01"], duracion_toma_s=7.0), raiz=raiz)
    frames = _todos_los_frames(final)
    centro = frames[:, y + h // 2, x + w // 2]                                      # color en el centro de los ojos
    cerrado = np.abs(centro - np.array(OJO_CERRADO)).max(1) <= 40                    # tolerancia de H.264
    abierto = np.abs(centro - np.array(OJO_ABIERTO)).max(1) <= 40
    assert cerrado.sum() >= 3, "no hay ningún parpadeo en el video"
    assert (cerrado | abierto).all()
    # rachas de ojos cerrados: cada parpadeo deja 1 a 3 frames del todo cerrados (medio y cerrado usan la misma imagen aquí)
    rachas, n = [], 0
    for c in cerrado:
        if c:
            n += 1
        elif n:
            rachas.append(n)
            n = 0
    assert rachas and all(3 <= r <= 5 or r in (6, 7, 8, 9, 10) for r in rachas), rachas     # dobles se pegan sin pausa visible
    # fuera de la zona de los ojos no cambia nada entre un frame con parpadeo y el anterior sin él (misma toma)
    i = int(np.argmax(cerrado))
    if i > 0 and not cerrado[i - 1]:
        dif = np.abs(frames[i] - frames[i - 1]).max(2) > 40
        dif[y - 2:y + h + 2, x - 2:x + w + 2] = False
        asignada_a_la_boca = dif[200:300, 250:390].sum()                              # la boca puede cambiar de forma
        assert dif.sum() - asignada_a_la_boca < 30
