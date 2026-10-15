"""T095 (FR-062, FR-067, FR-050): importar poses de la v3 y la calibración exportada por los
calibradores (un archivo con todas las poses o con una sola)."""
import json

import pytest
import yaml
from PIL import Image, ImageDraw

from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import VISEMAS, validar_pose
from src.errores import AssetInvalido

LIENZO = (320, 180)
VISTA = "tres_cuartos_der"


def _forma(i=0, m=False):
    return {"x": 150.0 + i, "y": 100.0, "s": 1.2, "r": 0.5 * i, "m": m}


def _formas():
    return {v: _forma(i) for i, v in enumerate(VISEMAS)}


def _imagen_pose(ruta, cabeza=(160, 50), modo="RGBA"):
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((cabeza[0] - 25, cabeza[1] - 25, cabeza[0] + 25, cabeza[1] + 25), fill=(230, 180, 150, 255))
    d.rectangle((cabeza[0] - 35, cabeza[1] + 25, cabeza[0] + 35, LIENZO[1]), fill=(245, 245, 245, 255))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    (im if modo == "RGBA" else im.convert("RGB")).save(ruta)
    return ruta


def _bocas(carpeta, prefijo="boca34_"):
    carpeta.mkdir(parents=True, exist_ok=True)
    for i, v in enumerate(VISEMAS):
        Image.new("RGBA", (30 + 3 * i, 14 + i), (200, 30, 30, 255)).save(carpeta / f"{prefijo}{v}.png")
    return carpeta


@pytest.fixture
def origen(proyecto_tmp):
    base = proyecto_tmp / "Torso Organizado" / "Tres cuartos derecha"
    _imagen_pose(base / f"{VISTA}_neutro_01.png", (160, 50))
    _imagen_pose(base / f"{VISTA}_explicar_01.png", (180, 60))
    _imagen_pose(base / f"{VISTA}_señalar_01.png", (150, 55))
    return base


def _calibracion(proyecto_tmp, poses, nombre="cal.json"):
    ruta = proyecto_tmp / nombre
    ruta.write_text(json.dumps({"version": 4, "juego": "tres_cuartos", "poses": poses}), encoding="utf-8")
    return ruta


def _importar(proyecto_tmp, origen, calibraciones=None, bocas=None):
    from src.biblioteca.calibraciones import importar_poses
    return importar_poses(origen, proyecto_tmp, "profe", calibraciones, bocas)


# ---------------- lectura de calibraciones ----------------
def test_se_lee_el_archivo_con_todas_las_poses(proyecto_tmp):
    from src.biblioteca.calibraciones import leer_calibraciones
    ruta = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()},
                                       f"{VISTA}_explicar_01": {"espejo": True, "formas": _formas()}})
    cal = leer_calibraciones(ruta)
    assert set(cal) == {f"{VISTA}_neutro_01", f"{VISTA}_explicar_01"} and cal[f"{VISTA}_explicar_01"]["espejo"] is True


def test_se_lee_el_archivo_de_una_sola_pose(proyecto_tmp):
    from src.biblioteca.calibraciones import leer_calibraciones
    ruta = proyecto_tmp / "una.json"
    ruta.write_text(json.dumps({"version": 4, "pose": f"{VISTA}_pulgar_01", "espejo": True, "formas": _formas()}),
                    encoding="utf-8")
    assert list(leer_calibraciones(ruta)) == [f"{VISTA}_pulgar_01"]


@pytest.mark.parametrize("texto", ["no es json", "[]", "{}", '{"poses": {}}'])
def test_calibraciones_vacias_o_malformadas_dan_un_error_claro(proyecto_tmp, texto):
    from src.biblioteca.calibraciones import leer_calibraciones
    ruta = proyecto_tmp / "mala.json"
    ruta.write_text(texto, encoding="utf-8")
    with pytest.raises(AssetInvalido) as exc:
        leer_calibraciones(ruta)
    assert exc.value.sugerencia


def test_formas_incompletas_nombran_la_pose_y_lo_que_falta(proyecto_tmp):
    from src.biblioteca.calibraciones import leer_calibraciones
    formas = {v: _forma() for v in VISEMAS if v not in ("F", "H")}
    ruta = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": formas}})
    with pytest.raises(AssetInvalido) as exc:
        leer_calibraciones(ruta)
    assert f"{VISTA}_neutro_01" in str(exc.value) and "F" in str(exc.value) and "H" in str(exc.value)


def test_un_archivo_que_no_existe_se_explica(proyecto_tmp):
    from src.biblioteca.calibraciones import leer_calibraciones
    with pytest.raises(AssetInvalido) as exc:
        leer_calibraciones(proyecto_tmp / "no_esta.json")
    assert "no_esta.json" in str(exc.value)


# ---------------- importar poses ----------------
def test_importa_cada_pose_con_su_cuerpo_y_su_config(proyecto_tmp, origen):
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()},
                                      f"{VISTA}_explicar_01": {"espejo": True, "formas": _formas()},
                                      f"{VISTA}_señalar_01": {"espejo": False, "formas": _formas()}})
    inf = _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "mis bocas")})
    poses_importadas = [i for i in inf.importados if not i.startswith("bocas ")]
    assert len(poses_importadas) == 3 and not inf.rechazados
    assert any(i.startswith("bocas de la vista") for i in inf.importados)
    poses = proyecto_tmp / "personajes" / "profe" / "poses"
    assert (poses / f"{VISTA}_señalar_01" / "cuerpo.png").is_file()
    pose = cargar_pose(poses / f"{VISTA}_explicar_01")
    assert (pose.vista, pose.gesto, pose.variante, pose.espejo, pose.lienzo) == (VISTA, "explicar", 1, True, LIENZO)
    assert pose.formas["D"].s == 1.2 and pose.pelo is not None


def test_el_centro_de_la_cabeza_queda_calculado_en_el_config(proyecto_tmp, origen):
    from src.alineacion import centro_cabeza
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()}})
    _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b")})
    pose = cargar_pose(proyecto_tmp / "personajes" / "profe" / "poses" / f"{VISTA}_neutro_01")
    esperado = centro_cabeza(Image.open(pose.ruta / "cuerpo.png"))
    assert pose.pelo == pytest.approx(esperado, abs=0.01)


def test_las_bocas_quedan_en_una_pose_dueña_y_las_demas_las_comparten(proyecto_tmp, origen):
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_{g}_01": {"espejo": False, "formas": _formas()}
                                      for g in ("neutro", "explicar", "señalar")})
    _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b")})
    poses = proyecto_tmp / "personajes" / "profe" / "poses"
    assert all((poses / f"{VISTA}_neutro_01" / "bocas" / f"{v}.png").is_file() for v in VISEMAS)
    explicar = cargar_pose(poses / f"{VISTA}_explicar_01")
    assert explicar.bocas_de == f"{VISTA}_neutro_01" and not (explicar.ruta / "bocas").exists()
    for carpeta in poses.iterdir():
        validar_pose(carpeta)                                      # todas quedan listas para renderizar


def test_los_sprites_pueden_llamarse_con_cualquier_prefijo(proyecto_tmp, origen):
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()}})
    inf = _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b", prefijo="boca_")})
    assert not inf.rechazados
    assert (proyecto_tmp / "personajes" / "profe" / "poses" / f"{VISTA}_neutro_01" / "bocas" / "G.png").is_file()


def test_si_faltan_bocas_se_rechaza_la_vista_con_lo_que_falta(proyecto_tmp, origen):
    carpeta = _bocas(proyecto_tmp / "b")
    (carpeta / "boca34_C.png").unlink()
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()}})
    inf = _importar(proyecto_tmp, origen, cal, {VISTA: carpeta})
    assert any("C" in r.motivo and "bocas" in r.motivo.lower() for r in inf.rechazados)


def test_una_pose_sin_calibracion_se_importa_pero_avisa(proyecto_tmp, origen):
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()}})
    inf = _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b")})
    assert any("explicar_01" in a and "calibr" in a.lower() for a in inf.avisos)
    pose_sin = proyecto_tmp / "personajes" / "profe" / "poses" / f"{VISTA}_explicar_01"
    assert (pose_sin / "cuerpo.png").is_file()
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(pose_sin)
    assert "calibr" in str(exc.value).lower()


def test_una_calibracion_sin_imagen_se_avisa(proyecto_tmp, origen):
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()},
                                      f"{VISTA}_bienvenida_03": {"espejo": False, "formas": _formas()}})
    inf = _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b")})
    assert any("bienvenida_03" in a for a in inf.avisos)


def test_una_imagen_sin_transparencia_se_rechaza(proyecto_tmp, origen):
    _imagen_pose(origen / f"{VISTA}_pulgar_01.png", modo="RGB")
    inf = _importar(proyecto_tmp, origen)
    r = next(r for r in inf.rechazados if "pulgar_01" in r.archivo)
    assert "transparencia" in r.motivo.lower()


def test_los_nombres_que_no_siguen_la_nomenclatura_se_ignoran_con_aviso(proyecto_tmp, origen):
    _imagen_pose(origen / "hoja de prueba.png")
    _imagen_pose(origen / f"{VISTA}_neutro_01_parpadeo.png")
    inf = _importar(proyecto_tmp, origen)
    assert not (proyecto_tmp / "personajes" / "profe" / "poses" / "hoja de prueba").exists()
    assert any("hoja de prueba.png" in r.archivo for r in inf.rechazados)
    assert not any("parpadeo" in i for i in inf.importados)           # los parpadeos se importan en T100


def test_importar_dos_veces_actualiza_la_calibracion_sin_duplicar(proyecto_tmp, origen):
    bocas = {VISTA: _bocas(proyecto_tmp / "b")}
    cal1 = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()}}, "c1.json")
    _importar(proyecto_tmp, origen, cal1, bocas)
    nuevas = _formas()
    nuevas["D"] = {"x": 222.0, "y": 111.0, "s": 0.5, "r": -2.0, "m": True}
    cal2 = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": True, "formas": nuevas}}, "c2.json")
    _importar(proyecto_tmp, origen, cal2, bocas)
    pose = cargar_pose(proyecto_tmp / "personajes" / "profe" / "poses" / f"{VISTA}_neutro_01")
    assert pose.espejo is True and pose.formas["D"].x == 222.0 and pose.formas["D"].m is True
    assert len(list((proyecto_tmp / "personajes" / "profe" / "poses").iterdir())) == 3


def test_el_tipo_de_cada_gesto_se_deduce_del_nombre(proyecto_tmp, origen):
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_{g}_01": {"espejo": False, "formas": _formas()}
                                      for g in ("neutro", "explicar", "señalar")})
    _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b")})
    poses = proyecto_tmp / "personajes" / "profe" / "poses"
    assert cargar_pose(poses / f"{VISTA}_neutro_01").tipo == "estado"
    assert cargar_pose(poses / f"{VISTA}_señalar_01").tipo == "acento"


def test_el_cli_importa_las_poses(proyecto_tmp, origen, capsys):
    from src.biblioteca.__main__ import main
    cal = _calibracion(proyecto_tmp, {f"{VISTA}_neutro_01": {"espejo": False, "formas": _formas()}})
    bocas = _bocas(proyecto_tmp / "b")
    codigo = main(["importar-poses", "--origen", str(origen), "--calibraciones", str(cal), "--bocas",
                   f"{VISTA}={bocas}", "--personaje", "profe", "--raiz", str(proyecto_tmp)])
    salida = capsys.readouterr().out
    assert codigo == 0 and "3 importadas" in salida
    assert (proyecto_tmp / "personajes" / "profe" / "poses" / f"{VISTA}_neutro_01" / "cuerpo.png").is_file()


# ---------------- nombres cortos de los calibradores (caso real: «explicar_01») ----------------
def _calibracion_corta(proyecto_tmp, nombres, juego="tres_cuartos", nombre="corta.json"):
    ruta = proyecto_tmp / nombre
    ruta.write_text(json.dumps({"version": 4, "juego": juego,
                                "poses": {n: {"espejo": n == "explicar_01", "formas": _formas()} for n in nombres}}),
                    encoding="utf-8")
    return ruta


def test_los_nombres_cortos_del_calibrador_se_asignan_a_la_pose_de_la_vista(proyecto_tmp, origen):
    cal = _calibracion_corta(proyecto_tmp, ["neutro_01", "explicar_01", "señalar_01"])
    inf = _importar(proyecto_tmp, origen, cal, {VISTA: _bocas(proyecto_tmp / "b")})
    assert not [a for a in inf.avisos if "sin calibración" in a or "ignora" in a]
    poses = proyecto_tmp / "personajes" / "profe" / "poses"
    assert cargar_pose(poses / f"{VISTA}_explicar_01").espejo is True
    assert cargar_pose(poses / f"{VISTA}_neutro_01").espejo is False


def test_un_nombre_corto_ambiguo_se_resuelve_con_el_juego_del_json(proyecto_tmp, origen):
    _imagen_pose(origen.parent / "Frontal" / "frontal_neutro_01.png")
    cal = _calibracion_corta(proyecto_tmp, ["neutro_01"], juego="tres_cuartos")
    inf = _importar(proyecto_tmp, [origen, origen.parent / "Frontal"], cal, {VISTA: _bocas(proyecto_tmp / "b")})
    poses = proyecto_tmp / "personajes" / "profe" / "poses"
    assert cargar_pose(poses / f"{VISTA}_neutro_01").formas["D"].s == 1.2           # la 3/4 quedó calibrada
    assert any("frontal_neutro_01" in a and "sin calibración" in a for a in inf.avisos)   # la frontal no


def test_un_nombre_corto_ambiguo_sin_juego_no_adivina(proyecto_tmp, origen):
    _imagen_pose(origen.parent / "Frontal" / "frontal_neutro_01.png")
    ruta = proyecto_tmp / "sinjuego.json"
    ruta.write_text(json.dumps({"version": 4, "poses": {"neutro_01": {"espejo": False, "formas": _formas()}}}),
                    encoding="utf-8")
    inf = _importar(proyecto_tmp, [origen, origen.parent / "Frontal"], ruta, {VISTA: _bocas(proyecto_tmp / "b")})
    assert any("neutro_01" in a and "ambigu" in a.lower() for a in inf.avisos)
