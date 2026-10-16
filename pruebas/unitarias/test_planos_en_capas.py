"""FR-053, FR-054, FR-044: la cámara virtual cambia de plano en cada toma (fondo y personaje), y entre dos poses la toma
nueva se mezcla unos frames con la anterior."""
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src import rutas
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import VISEMAS
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.concretas import FondoLayer
from src.layers.personaje import PersonajeLayer
from src.timeline import LineaDeTiempo, Toma, Visema

LIENZO = (640, 360)
SALIDA = (320, 180)
PIEL = (230, 180, 150)
FPS = 25


def _pose(raiz, nombre, cabeza=(320, 140), cuerpo=(245, 245, 245)):
    carpeta = raiz / "personajes" / "p" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    cx, cy = cabeza
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((cx - 80, cy + 50, cx + 80, LIENZO[1]), fill=(*cuerpo, 255))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(*PIEL, 255))
    im.save(carpeta / "cuerpo.png")
    for i, v in enumerate(VISEMAS):
        Image.new("RGBA", (30 + 2 * i, 12 + i), (200, 20, 20, 255)).save(carpeta / "bocas" / f"{v}.png")
    formas = {v: {"x": cx, "y": cy + 30, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), LIENZO, formas)
    return cargar_pose(carpeta)


def _ctx(toma, previa=None, mezcla=1.0, n=0):
    return ContextoFrame(n_frame=n, t=n / FPS, salida=SALIDA, toma=toma, visema="X", parpadeando=False,
                         escala=1.0, dx=0.0, dy=0.0, toma_previa=previa, mezcla=mezcla)


def _piel(capas):
    """Píxeles de piel en lo que dibujan las capas (todas apiladas)."""
    base = Image.new("RGBA", SALIDA, (0, 0, 0, 255))
    for c in capas:
        base.alpha_composite(c.imagen.crop((max(-c.x, 0), max(-c.y, 0), SALIDA[0] - c.x, SALIDA[1] - c.y)),
                             dest=(max(c.x, 0), max(c.y, 0)))
    a = np.asarray(base.convert("RGB")).astype(int)
    return int((np.abs(a - np.array(PIEL)).max(2) <= 6).sum())


# ---------------- personaje: un plano por toma ----------------
def test_el_personaje_usa_la_ventana_del_plano_de_cada_toma(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    ventanas = {pl: ventana_plano(pose, pl) for pl in ("PL2", "PL4")}
    capa = PersonajeLayer({pose.id: pose}, ventanas, SALIDA)
    lejos = _piel(capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL2"))))
    cerca = _piel(capa.renderizar(_ctx(Toma(50, "E1", pose.id, "PL4"))))
    assert cerca > 2 * lejos                                          # el plano cerrado agranda la cabeza


def test_un_plano_sin_ventana_da_un_error_claro(proyecto_tmp):
    from src.errores import AssetInvalido
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    capa = PersonajeLayer({pose.id: pose}, {"PL2": ventana_plano(pose, "PL2")}, SALIDA)
    with pytest.raises(AssetInvalido) as exc:
        capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL5")))
    assert "PL5" in str(exc.value) and "PL2" in str(exc.value)


def test_una_sola_ventana_sigue_funcionando_como_antes(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    capa = PersonajeLayer({pose.id: pose}, ventana_plano(pose, "PL3"), SALIDA)
    assert _piel(capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL3")))) > 0
    assert _piel(capa.renderizar(_ctx(Toma(50, "E1", pose.id, "PL5")))) > 0       # una ventana fija ignora el plano de la toma


# ---------------- fondo: un plano por toma ----------------
def test_el_fondo_estatico_se_recorta_segun_el_plano(proyecto_tmp):
    fondo = proyecto_tmp / "escenarios" / "E1_x" / "fondo.png"
    fondo.parent.mkdir(parents=True)
    im = Image.new("RGB", LIENZO, (0, 0, 0))
    ImageDraw.Draw(im).rectangle((300, 120, 340, 160), fill=(255, 255, 255))         # un cuadro blanco pequeño cerca de la cabeza
    im.save(fondo)
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    capa = FondoLayer(fondo, ventana_plano(pose, "PL2"), LIENZO, SALIDA, 0.0,
                      ventanas={pl: ventana_plano(pose, pl) for pl in ("PL2", "PL5")}, desenfoques={"PL2": 0.0, "PL5": 0.0})
    blanco = lambda c: int((np.asarray(c.imagen.convert("RGB")).astype(int).min(2) > 200).sum())
    assert blanco(capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL5")))) > 2 * blanco(capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL2"))))


@pytest.mark.skipif(not rutas.FFMPEG.exists(), reason="falta ffmpeg")
def test_el_fondo_en_video_cambia_de_recorte_al_cambiar_de_plano(proyecto_tmp):
    from src.layers.fondo_video import FondoVideoLayer
    ruta = proyecto_tmp / "escenarios" / "E1_calle" / "fondo.mp4"
    ruta.parent.mkdir(parents=True)
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate={FPS}:duration=4",
                    "-pix_fmt", "yuv420p", str(ruta)], check=True)
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    ventanas = {pl: ventana_plano(pose, pl) for pl in ("PL2", "PL5")}
    with FondoVideoLayer(ruta, ventanas["PL2"], LIENZO, SALIDA, FPS, cache_dir=proyecto_tmp / "cache",
                         ventanas=ventanas, desenfoques={"PL2": 0.0, "PL5": 0.0}) as capa:
        a = np.asarray(capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL2"), n=0)).imagen).astype(int)
        capa.renderizar(_ctx(Toma(0, "E1", pose.id, "PL2"), n=1))
        lanzados = capa.procesos_lanzados
        b = np.asarray(capa.renderizar(_ctx(Toma(2, "E1", pose.id, "PL5"), n=2)).imagen).astype(int)
        assert capa.procesos_lanzados == lanzados + 1                    # el recorte nuevo reabre el decodificador una vez
        capa.renderizar(_ctx(Toma(2, "E1", pose.id, "PL5"), n=3))
        assert capa.procesos_lanzados == lanzados + 1                    # y sigue en streaming dentro de la toma
        assert np.abs(a - b).mean() > 10                                 # y el encuadre es otro


# ---------------- mezcla de 2 frames entre poses ----------------
def test_durante_la_mezcla_se_ve_la_pose_anterior_debajo_de_la_nueva_semitransparente(proyecto_tmp):
    a = _pose(proyecto_tmp, "frontal_neutro_01", cuerpo=(255, 0, 0))
    b = _pose(proyecto_tmp, "frontal_explicar_01", cuerpo=(0, 0, 255))
    ventana = ventana_plano(a, "PL1")
    capa = PersonajeLayer({a.id: a, b.id: b}, ventana, SALIDA)
    previa, nueva = Toma(0, "E1", a.id, "PL1"), Toma(100, "E1", b.id, "PL1", 2)

    def color_cuerpo(capas):
        base = Image.new("RGBA", SALIDA, (0, 0, 0, 255))
        for c in capas:
            base.alpha_composite(c.imagen.crop((max(-c.x, 0), max(-c.y, 0), SALIDA[0] - c.x, SALIDA[1] - c.y)),
                                 dest=(max(c.x, 0), max(c.y, 0)))
        return np.asarray(base.convert("RGB"))[SALIDA[1] - 10, SALIDA[0] // 2].astype(int)

    sin = color_cuerpo(capa.renderizar(_ctx(nueva, None, 1.0, n=102)))
    mitad = color_cuerpo(capa.renderizar(_ctx(nueva, previa, 1 / 3, n=100)))
    assert tuple(sin) == (0, 0, 245) or (sin[2] > 200 and sin[0] < 20)                  # solo la pose nueva (azul)
    assert mitad[0] > 120 and mitad[2] > 50                                             # mezcla de rojo (anterior) y azul (nueva)
    assert mitad[0] > mitad[2]                                                          # con un tercio de la nueva, domina la anterior


def test_la_linea_de_tiempo_indica_la_toma_previa_y_el_peso_de_la_mezcla():
    tomas = [Toma(0, "E1", "a", "PL3"), Toma(100, "E1", "b", "PL3", 2), Toma(200, "E1", "b", "PL4", 0)]
    lt = LineaDeTiempo(FPS, 300, 1, [Visema(0, 300, "X")], tomas)
    assert lt.mezcla_en(99) == (None, 1.0)
    previa, w = lt.mezcla_en(100)
    assert previa == tomas[0] and w == pytest.approx(1 / 3)
    previa, w = lt.mezcla_en(101)
    assert previa == tomas[0] and w == pytest.approx(2 / 3)
    assert lt.mezcla_en(102) == (None, 1.0)
    assert lt.mezcla_en(200) == (None, 1.0)                                              # cambio de plano: corte seco


def test_las_tomas_con_mezcla_se_guardan_y_se_leen_en_la_linea_de_tiempo():
    lt = LineaDeTiempo(FPS, 300, 1, [Visema(0, 300, "X")], [Toma(0, "E1", "a", "PL3"), Toma(100, "E1", "b", "PL3", 2)])
    assert LineaDeTiempo.desde_json(lt.a_json()).tomas[1].mezcla == 2
    import json
    viejo = json.loads(lt.a_json())
    for t in viejo["tomas"]:
        t.pop("mezcla")
    assert LineaDeTiempo.desde_json(json.dumps(viejo)).tomas[1].mezcla == 0
