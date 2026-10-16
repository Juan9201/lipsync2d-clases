"""T099 (FR-040, FR-043, FR-049): parpadeo por imagen. Solo cambia la zona de los ojos, hay parpadeos dobles con su
probabilidad, nunca caen en un cambio de pose y una pose sin parpadeo avisa."""
import json

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from src.animation import generar_parpadeos
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import VISEMAS
from src.errores import ErrorAccionable
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.concretas import AnclasEstaticas, CuerpoLayer, OjosLayer
from src.timeline import LineaDeTiempo, Parpadeo, Toma, Visema

FPS = 25
N = 7500
LIENZO = (320, 180)
SALIDA = (320, 180)
PIEL = (230, 180, 150, 255)
CAJA = (130, 55, 60, 24)           # x, y, ancho, alto de los ojos en la pose de prueba


def _lt(parpadeos, n=400, tomas=None):
    return LineaDeTiempo(FPS, n, 1, [Visema(0, n, "X")], tomas or [Toma(0, "E1", "p", "PL1")], parpadeos)


# ---------------- línea de tiempo: fases de los ojos ----------------
def test_un_parpadeo_pasa_por_medio_cerrado_medio():
    lt = _lt([Parpadeo(100, 5)])
    fases = [lt.fase_ojos(f) for f in range(98, 107)]
    assert fases == ["abierto", "abierto", "medio", "cerrado", "cerrado", "cerrado", "medio", "abierto", "abierto"]
    assert lt.parpadeando(102) and not lt.parpadeando(105)


def test_un_parpadeo_de_tres_frames_tiene_un_solo_frame_cerrado():
    lt = _lt([Parpadeo(100, 3)])
    assert [lt.fase_ojos(f) for f in range(100, 103)] == ["medio", "cerrado", "medio"]


def test_un_parpadeo_doble_son_dos_parpadeos_con_una_pausa_corta():
    lt = _lt([Parpadeo(100, 4, doble=True)])
    fases = [lt.fase_ojos(f) for f in range(100, 100 + 4 + 3 + 4)]
    assert fases == ["medio", "cerrado", "cerrado", "medio", "abierto", "abierto", "abierto",
                     "medio", "cerrado", "cerrado", "medio"]
    assert lt.fase_ojos(100 + 11) == "abierto"


def test_la_validacion_cuenta_el_parpadeo_doble_completo_dentro_del_video():
    _lt([Parpadeo(380, 3, doble=True)]).validar()                         # 3+3+3 = 9 frames: cabe
    with pytest.raises(ErrorAccionable):
        _lt([Parpadeo(395, 4, doble=True)]).validar()                     # se sale del video


def test_la_linea_de_tiempo_guardada_antes_del_doble_se_sigue_leyendo():
    lt = _lt([Parpadeo(60, 4)])
    viejo = json.loads(lt.a_json())
    for p in viejo["parpadeos"]:
        p.pop("doble", None)
    assert LineaDeTiempo.desde_json(json.dumps(viejo)).parpadeos == [Parpadeo(60, 4, doble=False)]


# ---------------- generación: probabilidad de doble y cortes de pose ----------------
def test_la_fraccion_de_dobles_sigue_la_probabilidad_configurada():
    for prob in (0.10, 0.30):
        parp = generar_parpadeos(25 * 60 * 90, FPS, semilla=3, prob_doble=prob)         # ~1.300 parpadeos
        assert len(parp) >= 1000
        fraccion = sum(p.doble for p in parp) / len(parp)
        assert abs(fraccion - prob) <= 0.03, (prob, fraccion)


def test_por_defecto_el_10_por_ciento_son_dobles_y_se_puede_apagar():
    parp = generar_parpadeos(25 * 60 * 90, FPS, semilla=4)
    assert 0.07 <= sum(p.doble for p in parp) / len(parp) <= 0.13
    assert not any(p.doble for p in generar_parpadeos(25 * 60 * 90, FPS, semilla=4, prob_doble=0.0))


def test_ningun_parpadeo_cae_en_un_cambio_de_pose_y_los_intervalos_se_cumplen():
    cortes = list(range(150, 7500, 160))                                              # un corte cada 6,4 s
    parp = generar_parpadeos(N, FPS, semilla=9, prob_doble=0.5, cortes=cortes)
    assert len(parp) > 40
    for p in parp:
        span = p.span
        assert not any(p.f0 <= c < p.f0 + span for c in cortes), p
    for a, b in zip(parp, parp[1:]):
        assert 2 * FPS <= b.f0 - a.f0 <= 6 * FPS, (a, b)
    _lt(parp, n=N, tomas=[Toma(0, "E1", "p", "PL1")] + [Toma(c, "E1", "p", "PL1") for c in cortes]).validar()


def test_sin_cortes_ni_probabilidad_el_resultado_anterior_no_cambia():
    antes = generar_parpadeos(N, FPS, 5, prob_doble=0.0)
    assert [(p.f0, p.frames) for p in antes] == [(p.f0, p.frames) for p in generar_parpadeos(N, FPS, 5, prob_doble=0.0)]
    assert all(2 * FPS <= b.f0 - a.f0 <= 6 * FPS for a, b in zip(antes, antes[1:]))


# ---------------- importación del parpadeo y capa de ojos ----------------
def _pose_png(ruta, ojos_cerrados=False, cabeza=(160, 60)):
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = cabeza
    d.rectangle((cx - 50, cy + 30, cx + 50, LIENZO[1]), fill=(245, 245, 245, 255))
    d.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=PIEL)
    x, y, w, h = CAJA[0] + cx - 160, CAJA[1] + cy - 60, CAJA[2], CAJA[3]          # los ojos acompañan a la cabeza
    color = (30, 30, 30, 255) if ojos_cerrados else (255, 255, 255, 255)
    d.rectangle((x + 8, y + 8, x + w - 9, y + h - 9), fill=color)                 # los ojos
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta)
    return ruta


def _formas():
    return {v: {"x": 160, "y": 100, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}


def _cal_parpadeo(modo, poses, originales, borde=6):
    return {"modo": modo, "borde_suave_px": borde,
            "imagenes": {k: {"original": o, "centro": [0, 0], "desp": [0, 0]} for k, o in originales.items()},
            "cajas": {p: list(CAJA) for p in poses}}


@pytest.fixture
def escenario(proyecto_tmp):
    """Dos poses (neutro_01 y explicar_01) con la misma cabeza, bocas por vista y un parpadeo por pose."""
    from src.biblioteca.calibraciones import importar_poses
    base = proyecto_tmp / "Torso" / "Frontal"
    ids = ["frontal_neutro_01", "frontal_explicar_01"]
    for i in ids:
        _pose_png(base / f"{i}.png")
    blink = proyecto_tmp / "Torso" / "Blink"
    for i in ids:
        _pose_png(blink / f"{i}_parpadeo.png", ojos_cerrados=True)
    bocas = proyecto_tmp / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    cal = proyecto_tmp / "cal.json"
    cal.write_text(json.dumps({
        "version": 5, "juego": "frontal",
        "poses": {i: {"espejo": False, "formas": _formas()} for i in ids},
        "parpadeo": _cal_parpadeo("por_pose", ids, {i: f"{i}_parpadeo.png" for i in ids})}), encoding="utf-8")
    informe = importar_poses(base, proyecto_tmp, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink})
    return proyecto_tmp, informe, ids


def _ctx(fase, pose_id="frontal_neutro_01"):
    return ContextoFrame(n_frame=0, t=0.0, salida=SALIDA, toma=Toma(0, "E1", pose_id, "PL1"), visema="X",
                         parpadeando=fase != "abierto", escala=1.0, dx=0.0, dy=0.0, fase_ojos=fase)


def _capas(raiz, pose_id="frontal_neutro_01"):
    pose = cargar_pose(raiz / "personajes" / "profe" / "poses" / pose_id)
    v = ventana_plano(pose, "PL1")
    return pose, CuerpoLayer(pose, v, SALIDA), OjosLayer(pose, AnclasEstaticas(pose), v, SALIDA)


def _componer(cuerpo, ojos, ctx):
    from src.compositor import Compositor
    return np.asarray(Compositor([cuerpo, ojos], SALIDA).componer(ctx)).astype(int)


def test_la_importacion_deja_un_parche_pequeno_y_lo_registra_en_la_pose(escenario):
    raiz, informe, ids = escenario
    assert not [a for a in informe.avisos if "parpadeo" in a]
    carpeta = raiz / "personajes" / "profe" / "poses" / ids[0]
    cfg = yaml.safe_load((carpeta / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["parpadeo"]["parche"]["x"] <= CAJA[0] and cfg["parpadeo"]["parche"]["y"] <= CAJA[1]
    assert (carpeta / "parpadeo_cerrado.png").is_file() and not (carpeta / "parpadeo_medio.png").exists()
    with Image.open(carpeta / "parpadeo_cerrado.png") as p:
        assert p.width < LIENZO[0] / 2 and p.mode == "RGBA"
    assert cargar_pose(carpeta).parche_ojos is not None


def test_con_los_ojos_cerrados_solo_cambia_la_zona_de_los_ojos(escenario):
    raiz, _, _ = escenario
    pose, cuerpo, ojos = _capas(raiz)
    abierto, cerrado = _componer(cuerpo, ojos, _ctx("abierto")), _componer(cuerpo, ojos, _ctx("cerrado"))
    cambia = np.abs(abierto - cerrado).max(2) > 0
    assert cambia.sum() > 100                                                    # el parpadeo se ve
    ys, xs = np.where(cambia)
    x, y, w, h = CAJA
    margen = 8                                                                     # borde suave de 6 px
    assert xs.min() >= x - margen and xs.max() <= x + w + margen
    assert ys.min() >= y - margen and ys.max() <= y + h + margen


def test_fuera_del_parpadeo_la_capa_no_dibuja_nada(escenario):
    raiz, _, _ = escenario
    _, _, ojos = _capas(raiz)
    assert ojos.renderizar(_ctx("abierto")) is None


def test_sin_imagen_intermedia_la_fase_medio_usa_el_ojo_cerrado(escenario):
    raiz, _, _ = escenario
    _, cuerpo, ojos = _capas(raiz)
    assert (_componer(cuerpo, ojos, _ctx("medio")) == _componer(cuerpo, ojos, _ctx("cerrado"))).all()


def test_con_imagen_intermedia_la_fase_medio_se_ve_distinta_del_cerrado(proyecto_tmp):
    from src.biblioteca.calibraciones import importar_poses
    base = proyecto_tmp / "Torso" / "Frontal"
    _pose_png(base / "frontal_neutro_01.png")
    blink = proyecto_tmp / "Torso" / "Blink"
    _pose_png(blink / "cerrado.png", ojos_cerrados=True)
    medio = _pose_png(blink / "medio.png")
    ImageDraw.Draw(Image.open(medio)).rectangle((0, 0, 1, 1))                      # (solo asegura que existe)
    im = Image.open(medio).convert("RGBA")
    ImageDraw.Draw(im).rectangle((CAJA[0] + 8, CAJA[1] + 8, CAJA[0] + CAJA[2] - 9, CAJA[1] + 14), fill=(120, 120, 120, 255))
    im.save(medio)
    bocas = proyecto_tmp / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    cal = proyecto_tmp / "cal.json"
    cal.write_text(json.dumps({
        "version": 5, "juego": "frontal",
        "poses": {"frontal_neutro_01": {"espejo": False, "formas": _formas()}},
        "parpadeo": _cal_parpadeo("compartido", ["frontal_neutro_01"], {"cerrado": "cerrado.png", "medio": "medio.png"})}),
        encoding="utf-8")
    importar_poses(base, proyecto_tmp, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink})
    _, cuerpo, ojos = _capas(proyecto_tmp)
    medio_img, cerrado_img = _componer(cuerpo, ojos, _ctx("medio")), _componer(cuerpo, ojos, _ctx("cerrado"))
    assert (medio_img != cerrado_img).any()


def test_el_parpadeo_compartido_se_coloca_siguiendo_la_cabeza_de_cada_pose(proyecto_tmp):
    """Una sola imagen de parpadeo para dos poses con la cabeza en sitios distintos: cada parche cae sobre sus ojos."""
    from src.biblioteca.calibraciones import importar_poses
    base = proyecto_tmp / "Torso" / "Frontal"
    _pose_png(base / "frontal_neutro_01.png", cabeza=(160, 60))
    _pose_png(base / "frontal_explicar_01.png", cabeza=(190, 70))                  # 30 px a la derecha y 10 abajo
    blink = proyecto_tmp / "Torso" / "Blink"
    _pose_png(blink / "cerrado.png", ojos_cerrados=True, cabeza=(160, 60))
    bocas = proyecto_tmp / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    caja_b = [CAJA[0] + 30, CAJA[1] + 10, CAJA[2], CAJA[3]]
    cal = proyecto_tmp / "cal.json"
    cal.write_text(json.dumps({
        "version": 5, "juego": "frontal",
        "poses": {i: {"espejo": False, "formas": _formas()} for i in ("frontal_neutro_01", "frontal_explicar_01")},
        "parpadeo": {"modo": "compartido", "borde_suave_px": 4, "imagenes": {"cerrado": {"original": "cerrado.png", "desp": [0, 0]}},
                     "cajas": {"frontal_neutro_01": list(CAJA), "frontal_explicar_01": caja_b}}}), encoding="utf-8")
    importar_poses(base, proyecto_tmp, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink})
    for pose_id, caja in (("frontal_neutro_01", CAJA), ("frontal_explicar_01", caja_b)):
        _, cuerpo, ojos = _capas(proyecto_tmp, pose_id)
        a = _componer(cuerpo, ojos, _ctx("abierto", pose_id))
        c = _componer(cuerpo, ojos, _ctx("cerrado", pose_id))
        ys, xs = np.where(np.abs(a - c).max(2) > 0)
        # los ojos cerrados (gris oscuro) caen donde estaban los ojos abiertos (blancos) de esa pose
        x, y, w, h = caja
        assert abs(xs.mean() - (x + w / 2)) < 4 and abs(ys.mean() - (y + h / 2)) < 4, pose_id


def test_una_pose_sin_imagen_de_parpadeo_avisa_y_no_parpadea(proyecto_tmp):
    from src.biblioteca.calibraciones import importar_poses
    base = proyecto_tmp / "Torso" / "Frontal"
    _pose_png(base / "frontal_neutro_01.png")
    _pose_png(base / "frontal_libreta_01.png")
    blink = proyecto_tmp / "Torso" / "Blink"
    _pose_png(blink / "frontal_neutro_01_parpadeo.png", ojos_cerrados=True)        # a libreta_01 le falta
    bocas = proyecto_tmp / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    cal = proyecto_tmp / "cal.json"
    cal.write_text(json.dumps({
        "version": 5, "juego": "frontal",
        "poses": {i: {"espejo": False, "formas": _formas()} for i in ("frontal_neutro_01", "frontal_libreta_01")},
        "parpadeo": _cal_parpadeo("por_pose", ["frontal_neutro_01", "frontal_libreta_01"],
                                  {"frontal_neutro_01": "frontal_neutro_01_parpadeo.png"})}), encoding="utf-8")
    informe = importar_poses(base, proyecto_tmp, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink})
    assert any("frontal_libreta_01" in a and "parpadeo" in a for a in informe.avisos)
    _, cuerpo, ojos = _capas(proyecto_tmp, "frontal_libreta_01")
    assert ojos.renderizar(_ctx("cerrado", "frontal_libreta_01")) is None


def test_reimportar_sin_datos_de_parpadeo_conserva_el_parpadeo_ya_importado(escenario):
    from src.biblioteca.calibraciones import importar_poses
    raiz, _, ids = escenario
    carpeta = raiz / "personajes" / "profe" / "poses" / ids[0]
    antes = (carpeta / "parpadeo_cerrado.png").read_bytes()
    importar_poses(raiz / "Torso" / "Frontal", raiz, "profe")                       # sin calibración ni parpadeo
    assert (carpeta / "parpadeo_cerrado.png").read_bytes() == antes
    assert cargar_pose(carpeta).parche_ojos is not None


def test_el_parpadeo_sin_original_busca_los_nombres_del_proyecto(escenario):
    """Un JSON antiguo sin «original» se resuelve con la convención <pose>_parpadeo.png."""
    from src.biblioteca.calibraciones import importar_poses
    raiz, _, ids = escenario
    cal = raiz / "sin_original.json"
    cal.write_text(json.dumps({
        "version": 5, "juego": "frontal",
        "poses": {i: {"espejo": False, "formas": _formas()} for i in ids},
        "parpadeo": {"modo": "por_pose", "borde_suave_px": 6, "imagenes": {i: {"desp": [0, 0]} for i in ids},
                     "cajas": {i: list(CAJA) for i in ids}}}), encoding="utf-8")
    informe = importar_poses(raiz / "Torso" / "Frontal", raiz, "profe", cal, None, parpadeos={"frontal": raiz / "Torso" / "Blink"})
    assert not [a for a in informe.avisos if "parpadeo" in a]
