"""Un render real con un escenario de capas (fondo + frente + luces): se mide sobre el MP4 que la boca y los parpadeos caen donde deben,
que el frente tapa al personaje y que el director cambia de plano sin descolocar nada."""
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src import rutas
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import VISEMAS
from src.escena import config as cfgmod
from src.escena.escena import EscenaLayer
from src.render import ParametrosRender, renderizar

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (rutas.FFMPEG.exists() and rutas.RHUBARB.exists() and EJEMPLO.exists()),
                                 reason="faltan ffmpeg, Rhubarb o el audio de ejemplo")]

POSE = (640, 360)
SALIDA = (640, 360)
PIEL = (230, 180, 150)
BOCA = (200, 20, 20)
OJOS = (20, 20, 20)


def _pose(raiz, nombre):
    carpeta = raiz / "personajes" / "profe" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", POSE, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((230, 175, 410, 360), fill=(245, 245, 245, 255))
    d.ellipse((260, 60, 380, 180), fill=(*PIEL, 255))
    im.save(carpeta / "cuerpo.png")
    for v in VISEMAS:
        Image.new("RGBA", (50, 20), (*BOCA, 255)).save(carpeta / "bocas" / f"{v}.png")
    Image.new("RGBA", (60, 14), (*OJOS, 255)).save(carpeta / "parpadeo_cerrado.png")
    formas = {v: {"x": 320, "y": 160, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), POSE, formas,
                            parpadeo={"parche": {"x": 290, "y": 93}, "cerrado": "parpadeo_cerrado.png", "medio": None})
    return cargar_pose(carpeta)


@pytest.fixture
def clase(proyecto_tmp):
    poses = [_pose(proyecto_tmp, "frontal_neutro_01"), _pose(proyecto_tmp, "frontal_explicar_01")]
    esc = proyecto_tmp / "escenarios" / "E1_oficina"
    esc.mkdir(parents=True)
    fondo = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ImageDraw.Draw(fondo).rectangle((0, 0, 120, 120), fill=(0, 255, 0, 255))
    fondo.save(esc / "fondo.png")
    frente = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ImageDraw.Draw(frente).rectangle((0, 560, 1279, 719), fill=(255, 0, 255, 255))               # la mesa
    frente.save(esc / "frente.png")
    cfg = cfgmod.cargar_config(esc)
    cfg["personaje"].update({"cabeza": [760, 230], "escala": 1.0})
    cfg["luz"]["luces"] = [{"nombre": "lámpara", "pos": [300, 200], "color": [1, 0.8, 0.5], "fuerza": 1.0, "alcance": 800, "altura": 300}]
    cfgmod.guardar_config(esc, cfg)
    audio = proyecto_tmp / "clases" / "clase 01.mp3"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-t", "25", "-i", str(EJEMPLO), "-c", "copy", str(audio)], check=True)
    return proyecto_tmp, audio, poses, esc


def _frames(video):
    r = subprocess.run([str(rutas.FFMPEG), "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, SALIDA[1], SALIDA[0], 3).astype(int)


def _centro(frame, que):
    r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
    m = (r > 2 * g) & (r > 2 * b) & (r > 50) if que == "boca" else (np.maximum(np.maximum(r, g), b) < 55)
    m[:, :140] = False if que == "ojos" else m[:, :140]                      # el hueco oscuro no cuenta
    ys, xs = np.where(m)
    return (xs.mean(), ys.mean(), len(xs)) if len(xs) > 30 else None


def test_el_render_con_escena_pone_la_boca_y_los_parpadeos_donde_deben_y_el_frente_tapa(clase):
    raiz, audio, poses, esc = clase
    final = renderizar(ParametrosRender(personaje="profe", audio=audio, resolucion=SALIDA, semilla=1, escenario="E1",
                                        poses=["frontal_neutro_01"], plano="PL2", director=False), raiz=raiz)
    frames = _frames(final)
    capa = EscenaLayer(esc, cfgmod.cargar_config(esc), {poses[0].id: poses[0]}, SALIDA)
    q = lambda x, y: capa.a_pantalla(capa._esc * x + capa._t[0], capa._esc * y + capa._t[1], "PL2")
    eb, eo = q(320, 160), q(320, 100)
    bocas = [c for c in (_centro(f, "boca") for f in frames) if c]
    assert len(bocas) > 100
    assert abs(np.median([b[0] for b in bocas]) - eb[0]) < 3 and abs(np.median([b[1] for b in bocas]) - eb[1]) < 3
    ojos = [c for c in (_centro(f, "ojos") for f in frames) if c]
    assert ojos, "no hubo ningún parpadeo"
    assert abs(np.median([o[0] for o in ojos]) - eo[0]) < 4 and abs(np.median([o[1] for o in ojos]) - eo[1]) < 4
    # el frente (la «mesa») está encima del personaje en la parte baja del cuadro
    abajo = frames[len(frames) // 2][-10, SALIDA[0] // 2]
    assert abajo[0] > 200 and abajo[1] < 60 and abajo[2] > 200


def test_con_el_director_la_boca_sigue_sobre_la_cara_al_cambiar_de_plano_y_de_pose(clase):
    raiz, audio, poses, esc = clase
    import yaml
    cfg = cfgmod.cargar_config(esc)
    cfg["luz"]["luces"] = []                                                 # sin luz, para reconocer el color de la piel
    cfgmod.guardar_config(esc, cfg)
    reglas = raiz / "reglas.yaml"
    reglas.write_text(yaml.safe_dump({"toma_s": [3, 4], "acentos": {"activo": False}, "cambio": {"prob_plano": 0.6},
                                      "planos": {"permitidos": ["PL2", "PL3", "PL4"], "inicial": "PL3"}}), encoding="utf-8")
    final = renderizar(ParametrosRender(personaje="profe", audio=audio, resolucion=SALIDA, semilla=4, escenario="E1",
                                        poses=[p.id for p in poses], director=True, reglas=reglas), raiz=raiz)
    frames = _frames(final)
    tamanos, desviaciones = set(), []
    for f in frames[::3]:
        cara = (np.abs(f - np.array(PIEL)).max(2) <= 14)
        boca = _centro(f, "boca")
        ys, xs = np.where(cara)
        if boca and len(xs) > 500:
            tamanos.add(int(round((ys.max() - ys.min()) / 20)))
            desviaciones.append(abs(boca[0] - xs.mean()))                    # la boca está en el eje de la cara
    assert len(tamanos) >= 2, "la cámara no cambió de plano"
    assert max(desviaciones) < 12 and np.median(desviaciones) < 5


def test_poses_permitidas_del_escenario_limitan_al_director(clase):
    raiz, audio, poses, esc = clase
    cfg = cfgmod.cargar_config(esc)
    cfg["poses_permitidas"] = ["frontal_neutro_01"]
    cfgmod.guardar_config(esc, cfg)
    final = renderizar(ParametrosRender(personaje="profe", audio=audio, resolucion=SALIDA, semilla=2, escenario="E1",
                                        poses=[p.id for p in poses], director=True), raiz=raiz)
    log = (raiz / "logs" / f"{audio.stem}.log").read_text(encoding="utf-8")
    assert "frontal_explicar_01" not in log and final.exists()
