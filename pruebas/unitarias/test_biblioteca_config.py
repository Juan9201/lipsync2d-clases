"""FR-050, FR-051, FR-052: modelo de pose/escenario y carga de config.yaml."""
import pytest
import yaml

from src.biblioteca.modelos import cargar_escenario, cargar_pose
from src.errores import AssetInvalido

CONFIG_POSE = {
    "version": 1, "id": "P3", "nombre": "explicando", "lienzo": [3840, 2160],
    "espejo": False, "bocas_de": None,
    "anclas": {
        "boca": {"x": 1980, "y": 610, "ancho": 96, "angulo": 0.0},
        "ojos": {"x": 1980, "y": 520, "ancho": 210, "angulo": 0.0},
        "cabeza": {"x": 1980, "y": 560},
    },
}


def _pose(proyecto, config=None, carpeta="P3_explicando"):
    ruta = proyecto / "personajes" / "profesor" / "poses" / carpeta
    ruta.mkdir(parents=True)
    (ruta / "config.yaml").write_text(
        yaml.safe_dump(config or CONFIG_POSE, allow_unicode=True), encoding="utf-8")
    return ruta


def test_carga_pose_completa(proyecto_tmp):
    pose = cargar_pose(_pose(proyecto_tmp))
    assert pose.id == "P3" and pose.nombre == "explicando"
    assert pose.lienzo == (3840, 2160)
    assert pose.anclas.boca.x == 1980 and pose.anclas.boca.ancho == 96
    assert pose.anclas.cabeza.y == 560
    assert pose.espejo is False and pose.bocas_de is None


def test_valores_por_defecto_de_planos_y_movimiento(proyecto_tmp):
    pose = cargar_pose(_pose(proyecto_tmp))
    assert pose.planos["PL1"].alto_relativo == 1.0
    assert pose.planos["PL4"].alto_relativo == 0.42
    assert set(pose.planos) == {"PL1", "PL2", "PL3", "PL4", "PL5", "PL6"}
    assert pose.movimiento.respiracion_escala == 0.0 and pose.movimiento.cabeza_px == 0.0   # apagados por defecto


def test_planos_de_la_pose_sustituyen_los_por_defecto(proyecto_tmp):
    cfg = dict(CONFIG_POSE, planos={"PL4": {"alto_relativo": 0.5, "centro_y_relativo": 0.3}})
    pose = cargar_pose(_pose(proyecto_tmp, cfg))
    assert pose.planos["PL4"].alto_relativo == 0.5
    assert pose.planos["PL3"].alto_relativo == 0.58


def test_espejo_y_bocas_de(proyecto_tmp):
    cfg = dict(CONFIG_POSE, espejo=True, bocas_de="P1")
    pose = cargar_pose(_pose(proyecto_tmp, cfg))
    assert pose.espejo is True and pose.bocas_de == "P1"


def test_id_distinto_de_la_carpeta_da_error(proyecto_tmp):
    ruta = _pose(proyecto_tmp, carpeta="P9_otra")
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(ruta)
    assert "P3" in str(exc.value) and "P9_otra" in str(exc.value)


def test_ancla_fuera_del_lienzo_da_error(proyecto_tmp):
    cfg = dict(CONFIG_POSE)
    cfg["anclas"] = dict(CONFIG_POSE["anclas"], boca={"x": 9999, "y": 10, "ancho": 50, "angulo": 0})
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(_pose(proyecto_tmp, cfg))
    assert "boca" in str(exc.value)


def test_sin_config_da_error_accionable(proyecto_tmp):
    ruta = proyecto_tmp / "personajes" / "profesor" / "poses" / "P3_x"
    ruta.mkdir(parents=True)
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(ruta)
    assert "config.yaml" in str(exc.value)


def _escenario(proyecto, config=None, carpeta="E2_salon"):
    ruta = proyecto / "escenarios" / carpeta
    ruta.mkdir(parents=True)
    if config is not None:
        (ruta / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return ruta


def test_escenario_sin_config_admite_todo(proyecto_tmp):
    esc = cargar_escenario(_escenario(proyecto_tmp))
    assert esc.id == "E2" and esc.nombre == "salon"
    assert esc.admite("P7", "PL6")


def test_escenario_con_restricciones(proyecto_tmp):
    esc = cargar_escenario(_escenario(proyecto_tmp, {
        "version": 1, "id": "E2", "planos_permitidos": ["PL2", "PL3"], "poses_permitidas": ["P1"]}))
    assert esc.admite("P1", "PL2")
    assert not esc.admite("P1", "PL5")
    assert not esc.admite("P2", "PL2")


def test_movimiento_se_puede_activar_por_pose(proyecto_tmp):
    cfg = dict(CONFIG_POSE, movimiento={"respiracion_escala": 0.005, "cabeza_px": 6})
    pose = cargar_pose(_pose(proyecto_tmp, cfg))
    assert pose.movimiento.respiracion_escala == 0.005 and pose.movimiento.cabeza_px == 6


def test_ojos_de_es_independiente_de_bocas_de(proyecto_tmp):
    cfg = dict(CONFIG_POSE, bocas_de="P1", ojos_de="P2")
    pose = cargar_pose(_pose(proyecto_tmp, cfg))
    assert pose.bocas_de == "P1" and pose.ojos_de == "P2"
    assert cargar_pose(_pose(proyecto_tmp, dict(CONFIG_POSE, id="P4"), carpeta="P4_x")).ojos_de is None
