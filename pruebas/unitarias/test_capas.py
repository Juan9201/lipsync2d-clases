"""FR-030: capas concretas (fondo, cuerpo, ojos, boca) con el plano PL1."""
import pytest
from PIL import Image

from src.biblioteca.modelos import cargar_pose
from src.biblioteca.placeholders import crear_pose_placeholder
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.concretas import AnclasEstaticas, BocaLayer, CuerpoLayer, FondoLayer, OjosLayer

SALIDA = (160, 90)


@pytest.fixture
def pose(proyecto_tmp):
    carpeta = proyecto_tmp / "personajes" / "p" / "poses" / "P1_x"
    crear_pose_placeholder(carpeta, "P1", lienzo=(320, 180))
    return cargar_pose(carpeta)


def _ctx(visema="X", parpadeando=False):
    return ContextoFrame(n_frame=0, t=0.0, salida=SALIDA, toma=None, visema=visema,
                         parpadeando=parpadeando, escala=1.0, dx=0.0, dy=0.0)


def test_cuerpo_cubre_la_salida_en_pl1(pose):
    capa = CuerpoLayer(pose, ventana_plano(pose, "PL1"), SALIDA).renderizar(_ctx())
    assert capa.imagen.size == SALIDA and (capa.x, capa.y) == (0, 0) and capa.imagen.mode == "RGBA"


def test_boca_se_posiciona_centrada_en_el_ancla_escalada(pose):
    anclas = AnclasEstaticas(pose)
    capa = BocaLayer(pose, anclas, ventana_plano(pose, "PL1"), SALIDA).renderizar(_ctx("D"))
    esc = SALIDA[0] / pose.lienzo[0]
    cx, cy = capa.x + capa.imagen.width / 2, capa.y + capa.imagen.height / 2
    assert cx == pytest.approx(pose.anclas.boca.x * esc, abs=1.5)
    assert cy == pytest.approx(pose.anclas.boca.y * esc, abs=1.5)
    assert capa.imagen.width == pytest.approx(pose.anclas.boca.ancho * esc, abs=1.5)


def test_cada_visema_da_una_imagen_distinta(pose):
    capa = BocaLayer(pose, AnclasEstaticas(pose), ventana_plano(pose, "PL1"), SALIDA)
    huellas = {v: capa.renderizar(_ctx(v)).imagen.tobytes() for v in "ABCDEFGHX"}
    assert len(set(huellas.values())) == 9


def test_boca_con_angulo_rota_la_imagen(pose, proyecto_tmp):
    import yaml
    cfg_ruta = pose.ruta / "config.yaml"
    cfg = yaml.safe_load(cfg_ruta.read_text(encoding="utf-8"))
    cfg["anclas"]["boca"]["angulo"] = 20.0
    cfg_ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    girada = cargar_pose(pose.ruta)
    recta = BocaLayer(pose, AnclasEstaticas(pose), ventana_plano(pose, "PL1"), SALIDA).renderizar(_ctx("D"))
    con_giro = BocaLayer(girada, AnclasEstaticas(girada), ventana_plano(girada, "PL1"), SALIDA).renderizar(_ctx("D"))
    assert con_giro.imagen.size != recta.imagen.size


def test_ojos_solo_aparecen_al_parpadear(pose):
    capa = OjosLayer(pose, AnclasEstaticas(pose), ventana_plano(pose, "PL1"), SALIDA)
    assert capa.renderizar(_ctx(parpadeando=False)) is None
    assert capa.renderizar(_ctx(parpadeando=True)) is not None


def test_fondo_de_escenario_cubre_la_salida(pose, proyecto_tmp):
    ruta = proyecto_tmp / "escenarios" / "E1_x" / "fondo.png"
    ruta.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), (10, 200, 30)).save(ruta)
    capa = FondoLayer(ruta, ventana_plano(pose, "PL1"), pose.lienzo, SALIDA, desenfoque=0).renderizar(_ctx())
    assert capa.imagen.size == SALIDA and capa.imagen.getpixel((5, 5))[:3] == (10, 200, 30)


def test_sin_escenario_no_hay_capa_de_fondo(pose):
    assert FondoLayer(None, ventana_plano(pose, "PL1"), pose.lienzo, SALIDA, 0).renderizar(_ctx()) is None


def test_anclas_estaticas_devuelven_las_de_la_pose(pose):
    assert AnclasEstaticas(pose).anclas(123, "P1") == pose.anclas


# ---------------- US3: movimiento y respiración en las capas ----------------
@pytest.fixture
def pose_mov(pose):
    """La misma pose con respiración y movimiento activados (están apagados por defecto)."""
    import yaml
    ruta = pose.ruta / "config.yaml"
    cfg = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    cfg["movimiento"] = {"respiracion_escala": 0.005, "cabeza_px": 6}
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return cargar_pose(pose.ruta)


def _ctx_mov(escala=1.0, dx=0.0, dy=0.0, visema="D", parpadeando=False):
    return ContextoFrame(n_frame=0, t=0.0, salida=SALIDA, toma=None, visema=visema,
                         parpadeando=parpadeando, escala=escala, dx=dx, dy=dy)


def test_cuerpo_con_respiracion_cambia_de_tamano_o_posicion_y_cubre_los_bordes(pose_mov):
    capa = CuerpoLayer(pose_mov, ventana_plano(pose_mov, "PL1"), SALIDA)
    quieto = capa.renderizar(_ctx_mov())
    resp = capa.renderizar(_ctx_mov(escala=1.005))
    assert (quieto.imagen.size, quieto.x, quieto.y) == (SALIDA, 0, 0)       # reposo: camino rápido
    assert resp.imagen.width >= SALIDA[0] and resp.x <= 0 and resp.y <= 0   # con margen de relleno
    assert resp.imagen.width + resp.x >= SALIDA[0] and resp.imagen.height + resp.y >= SALIDA[1]


def test_la_boca_acompana_al_cuerpo_con_el_mismo_desplazamiento(pose_mov):
    v = ventana_plano(pose_mov, "PL1")
    boca = BocaLayer(pose_mov, AnclasEstaticas(pose_mov), v, SALIDA)
    base = boca.renderizar(_ctx_mov())
    movida = boca.renderizar(_ctx_mov(dx=8.0, dy=-4.0))
    esc = SALIDA[0] / pose_mov.lienzo[0]
    assert movida.x - base.x == round(8.0 * esc) and movida.y - base.y == round(-4.0 * esc)
    cuerpo = CuerpoLayer(pose_mov, v, SALIDA)
    c0, c1 = cuerpo.renderizar(_ctx_mov()), cuerpo.renderizar(_ctx_mov(dx=8.0, dy=-4.0))
    from src.layers.concretas import MARGEN_MOV
    # el cuerpo en movimiento lleva MARGEN_MOV de relleno; descontado, el desplazamiento coincide
    assert (c1.x + MARGEN_MOV - c0.x, c1.y + MARGEN_MOV - c0.y) == (movida.x - base.x, movida.y - base.y)


def test_la_boca_se_escala_con_la_respiracion_respecto_al_pivote_inferior(pose_mov):
    v = ventana_plano(pose_mov, "PL1")
    boca = BocaLayer(pose_mov, AnclasEstaticas(pose_mov), v, SALIDA)
    reposo, inhala = boca.renderizar(_ctx_mov()), boca.renderizar(_ctx_mov(escala=1.01))
    cy0 = reposo.y + reposo.imagen.height / 2
    cy1 = inhala.y + inhala.imagen.height / 2
    assert cy1 < cy0                                  # al inhalar la cabeza sube (el pie queda fijo)
    assert inhala.imagen.width >= reposo.imagen.width


def test_el_parpadeo_se_ve_en_el_frame(pose):
    from src.compositor import Compositor
    v = ventana_plano(pose, "PL1")
    anclas = AnclasEstaticas(pose)
    comp = Compositor([CuerpoLayer(pose, v, SALIDA), OjosLayer(pose, anclas, v, SALIDA)], SALIDA)
    abierto = comp.componer(_ctx_mov(parpadeando=False))
    cerrado = comp.componer(_ctx_mov(parpadeando=True))
    assert abierto.tobytes() != cerrado.tobytes()
