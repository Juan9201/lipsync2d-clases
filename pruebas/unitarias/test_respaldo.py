"""FR-083, FR-084: modo de respaldo = imagen completa como capa base de una toma fija."""
from pathlib import Path

import pytest
from PIL import Image

from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import validar_pose
from src.prep.respaldo import crear_pose_respaldo


@pytest.fixture
def imagen(proyecto_tmp) -> Path:
    ruta = proyecto_tmp / "entrada" / "profesor ñ.png"
    im = Image.new("RGBA", (320, 180), (200, 210, 220, 255))
    im.putpixel((5, 5), (255, 0, 0, 255))
    im.save(ruta)
    return ruta


def _pose_dir(proyecto):
    return proyecto / "personajes" / "profesor" / "poses" / "P1_profesor"


def test_crea_pose_valida_en_modo_respaldo(proyecto_tmp, imagen):
    r = crear_pose_respaldo(imagen, _pose_dir(proyecto_tmp), "P1", boca=(200, 100, 40))
    assert r.creada
    pose = validar_pose(_pose_dir(proyecto_tmp))
    assert pose.respaldo is True
    assert pose.movimiento.respiracion_escala == 0 and pose.movimiento.cabeza_px == 0
    assert (pose.anclas.boca.x, pose.anclas.boca.y, pose.anclas.boca.ancho) == (200, 100, 40)


def test_el_cuerpo_es_la_imagen_completa_opaca(proyecto_tmp, imagen):
    crear_pose_respaldo(imagen, _pose_dir(proyecto_tmp), "P1")
    with Image.open(_pose_dir(proyecto_tmp) / "cuerpo.png") as cuerpo:
        assert cuerpo.mode == "RGBA" and cuerpo.size == (320, 180)
        assert cuerpo.getpixel((5, 5)) == (255, 0, 0, 255)
        assert cuerpo.getchannel("A").getextrema() == (255, 255)


def test_segunda_ejecucion_no_repite_la_preparacion(proyecto_tmp, imagen):
    d = _pose_dir(proyecto_tmp)
    crear_pose_respaldo(imagen, d, "P1")
    antes = (d / "cuerpo.png").stat().st_mtime_ns
    r = crear_pose_respaldo(imagen, d, "P1")
    assert not r.creada
    assert (d / "cuerpo.png").stat().st_mtime_ns == antes
    assert any("ya estaba preparada" in a for a in r.avisos)


def test_forzar_repite(proyecto_tmp, imagen):
    d = _pose_dir(proyecto_tmp)
    crear_pose_respaldo(imagen, d, "P1")
    assert crear_pose_respaldo(imagen, d, "P1", forzar=True).creada


def test_anclas_por_defecto_quedan_dentro_del_lienzo_y_avisan(proyecto_tmp, imagen):
    r = crear_pose_respaldo(imagen, _pose_dir(proyecto_tmp), "P1")
    pose = cargar_pose(_pose_dir(proyecto_tmp))
    assert 0 < pose.anclas.boca.x < 320 and 0 < pose.anclas.ojos.y < 180
    assert any("calibra" in a.lower() for a in r.avisos)


def test_imagen_no_16_9_se_ajusta_y_avisa(proyecto_tmp):
    ruta = proyecto_tmp / "entrada" / "cuadrada.png"
    Image.new("RGB", (300, 300), (1, 2, 3)).save(ruta)
    r = crear_pose_respaldo(ruta, _pose_dir(proyecto_tmp), "P1", modo_formato="recortar")
    assert cargar_pose(_pose_dir(proyecto_tmp)).lienzo == (300, 169)
    assert any("no es 16:9" in a for a in r.avisos)


def test_incluye_bocas_y_ojos_placeholder_para_el_parpadeo(proyecto_tmp, imagen):
    d = _pose_dir(proyecto_tmp)
    crear_pose_respaldo(imagen, d, "P1")
    assert (d / "ojos_cerrados.png").is_file()
    assert len(list((d / "bocas").glob("*.png"))) == 9
