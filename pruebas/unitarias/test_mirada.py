"""Poses con contacto visual (`..._eye_contact`): el sistema las reconoce, sabe si una pose mira a la cámara o de lado, y el director no deja
mucho tiempo las poses 3/4 que miran de lado (las prefiere poco y las corta pronto)."""
from collections import Counter
from types import SimpleNamespace

import pytest
from PIL import Image

from src.biblioteca.calibraciones import importar_poses
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import _NOMBRE_POSE_V3, cargar_pose
from src.biblioteca.validacion import VISEMAS
from src.director import cargar_reglas, dirigir
from src.errores import ErrorAccionable
from src.timeline import Visema

FPS = 25
N = 280 * FPS


# ---------------------------------------------------------------- nombres y atributo «mirada»
@pytest.mark.parametrize("nombre,vista,gesto,nn,sufijo", [
    ("tres_cuartos_der_neutro_01", "tres_cuartos_der", "neutro", "01", None),
    ("tres_cuartos_der_neutro_01_eye_contact", "tres_cuartos_der", "neutro", "01", "_eye_contact"),
    ("tres_cuartos_der_señalar_01_eye_contacts", "tres_cuartos_der", "señalar", "01", "_eye_contacts"),
    ("frontal_explicar_02", "frontal", "explicar", "02", None)])
def test_el_nombre_de_pose_acepta_el_sufijo_de_contacto_visual(nombre, vista, gesto, nn, sufijo):
    m = _NOMBRE_POSE_V3.match(nombre)
    assert m and (m.group("vista"), m.group("gesto"), m.group("nn"), m.group("mirada")) == (vista, gesto, nn, sufijo)


@pytest.mark.parametrize("nombre", ["tres_cuartos_der_neutro_01_otra_cosa", "tres_cuartos_der_neutro_eye_contact"])
def test_otros_sufijos_siguen_rechazados(nombre):
    assert not _NOMBRE_POSE_V3.match(nombre)


def _pose_en_disco(raiz, nombre, vista, gesto, nn, extra=None):
    carpeta = raiz / nombre
    (carpeta / "bocas").mkdir(parents=True)
    Image.new("RGBA", (400, 300), (0, 0, 0, 0)).save(carpeta / "cuerpo.png")
    for v in VISEMAS:
        Image.new("RGBA", (10, 6), (200, 20, 20, 255)).save(carpeta / "bocas" / f"{v}.png")
    formas = {v: {"x": 200, "y": 150, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    escribir_config_pose_v4(carpeta, vista, gesto, nn, (400, 300), formas)
    if extra:
        import yaml
        cfg = yaml.safe_load((carpeta / "config.yaml").read_text(encoding="utf-8"))
        cfg.update(extra)
        (carpeta / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return carpeta


def test_la_mirada_de_cada_pose_sale_de_su_vista_y_de_su_sufijo(tmp_path):
    casos = {"frontal_neutro_01": ("frontal", "neutro", 1, "camara"),
             "tres_cuartos_der_neutro_01": ("tres_cuartos_der", "neutro", 1, "lateral"),
             "tres_cuartos_der_neutro_01_eye_contact": ("tres_cuartos_der", "neutro", 1, "camara"),
             "tres_cuartos_der_señalar_01_eye_contacts": ("tres_cuartos_der", "señalar", 1, "camara")}
    for nombre, (vista, gesto, nn, esperada) in casos.items():
        pose = cargar_pose(_pose_en_disco(tmp_path, nombre, vista, gesto, nn))
        assert (pose.id, pose.vista, pose.gesto, pose.variante, pose.mirada) == (nombre, vista, gesto, nn, esperada), nombre


def test_la_config_de_la_pose_puede_forzar_la_mirada(tmp_path):
    pose = cargar_pose(_pose_en_disco(tmp_path, "tres_cuartos_der_pulgar_01", "tres_cuartos_der", "pulgar", 1, {"mirada": "camara"}))
    assert pose.mirada == "camara"


def test_el_importador_acepta_las_poses_eye_contact_y_no_las_rechaza(proyecto_tmp):
    base = proyecto_tmp / "Torso" / "Tres cuartos"
    base.mkdir(parents=True)
    for n in ("tres_cuartos_der_neutro_01", "tres_cuartos_der_neutro_01_eye_contact", "tres_cuartos_der_señalar_01_eye_contacts"):
        im = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
        im.paste((230, 180, 150, 255), (150, 60, 250, 160))
        im.save(base / f"{n}.png")
    informe = importar_poses(base, proyecto_tmp, "profe")
    assert not informe.rechazados
    poses = proyecto_tmp / "personajes" / "profe" / "poses"
    assert {d.name for d in poses.iterdir()} == {"tres_cuartos_der_neutro_01", "tres_cuartos_der_neutro_01_eye_contact",
                                                  "tres_cuartos_der_señalar_01_eye_contacts"}


# ---------------------------------------------------------------- director
def _p(id_, mirada=None, tipo="estado"):
    p = SimpleNamespace(id=id_, vista=id_.rsplit("_", 2)[0], gesto=id_.rsplit("_", 2)[1], tipo=tipo, variante=1)
    if mirada:
        p.mirada = mirada
    return p


CAMARA = [_p("frontal_neutro_01", "camara"), _p("frontal_explicar_01", "camara"), _p("tres_cuartos_der_neutro_01_eye_contact", "camara")]
LATERAL = [_p("tres_cuartos_der_neutro_01", "lateral"), _p("tres_cuartos_der_libreta_03", "lateral")]


def _visemas(n=N, cada_s=2.2, pausa_f=8):
    v, f = [], 0
    while f < n:
        habla = min(round(cada_s * FPS) - pausa_f, n - f)
        v.append(Visema(f, f + habla, "D"))
        f += habla
        if f < n:
            v.append(Visema(f, min(f + pausa_f, n), "X"))
            f = min(f + pausa_f, n)
    return v


def _tomas(poses, semilla=1, reglas=None, n=N):
    return dirigir(poses, _visemas(n), n, FPS, "E1", semilla, cargar_reglas(None, reglas))


def _duraciones(tomas, n=N):
    fin = [t.f0 for t in tomas[1:]] + [n]
    return [(t.pose, (e - t.f0) / FPS) for t, e in zip(tomas, fin)]


def test_una_pose_que_mira_de_lado_nunca_dura_mas_de_lo_permitido():
    for semilla in range(8):
        tomas = _tomas(CAMARA + LATERAL, semilla, {"mirada": {"lateral_max_s": 4}})
        lat = {p.id for p in LATERAL}
        largas = [(p, d) for p, d in _duraciones(tomas) if p in lat and d > 4 + 1.0]
        assert not largas, (semilla, largas)


def test_tras_una_pose_de_lado_siempre_cambia_la_pose_no_solo_el_plano():
    lat = {p.id for p in LATERAL}
    for semilla in range(6):
        t = _tomas(CAMARA + LATERAL, semilla)
        for a, b in zip(t, t[1:]):
            if a.pose in lat:
                assert b.pose != a.pose, (semilla, a, b)


def test_las_poses_que_miran_de_lado_se_eligen_mucho_menos_que_las_de_contacto_visual():
    por_pose = Counter()
    for semilla in range(14):
        por_pose.update(t.pose for t in _tomas(CAMARA + LATERAL, semilla)[1:])
    lat = sum(por_pose[p.id] for p in LATERAL) / len(LATERAL)
    cam = sum(por_pose[p.id] for p in CAMARA) / len(CAMARA)
    assert lat < 0.35 * cam, (dict(por_pose),)


def test_con_peso_uno_y_sin_limite_el_director_se_comporta_como_antes():
    reglas = {"mirada": {"lateral_max_s": 0, "peso_lateral": 1.0}}
    por_pose = Counter()
    largas = 0
    for semilla in range(10):
        t = _tomas(CAMARA + LATERAL, semilla, reglas)
        por_pose.update(x.pose for x in t[1:])
        largas += sum(1 for p, d in _duraciones(t) if p in {x.id for x in LATERAL} and d > 5)
    lat = sum(por_pose[p.id] for p in LATERAL) / len(LATERAL)
    cam = sum(por_pose[p.id] for p in CAMARA) / len(CAMARA)
    assert lat > 0.6 * cam and largas > 0


def test_sin_atributo_mirada_las_poses_cuentan_como_de_contacto_visual():
    sin = [_p("frontal_neutro_01"), _p("frontal_explicar_01"), _p("frontal_libreta_01")]
    tomas = _tomas(sin, 3)
    assert max(d for _, d in _duraciones(tomas)) > 5                          # no se les aplica el límite corto


@pytest.mark.parametrize("cambio", [{"mirada": {"lateral_max_s": -1}}, {"mirada": {"peso_lateral": 0}}, {"mirada": {"peso_lateral": 1.5}}])
def test_las_reglas_de_mirada_invalidas_se_rechazan(cambio):
    with pytest.raises(ErrorAccionable):
        cargar_reglas(None, cambio)
