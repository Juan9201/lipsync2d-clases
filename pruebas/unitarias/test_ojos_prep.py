"""Párpado de prueba generado desde la imagen de la pose (parpadeo mientras no hay ojos definitivos)."""
import yaml
from PIL import Image

from src.prep.ojos import regenerar_ojos
from src.prep.respaldo import crear_pose_respaldo


def _pose(proyecto):
    imagen = proyecto / "entrada" / "p.png"
    Image.new("RGB", (640, 360), (225, 175, 140)).save(imagen)
    carpeta = proyecto / "personajes" / "profesor" / "poses" / "P1_profesor"
    crear_pose_respaldo(imagen, carpeta, "P1")
    (carpeta / "original.png").write_bytes(imagen.read_bytes())
    return carpeta


def test_la_pose_de_respaldo_trae_ojos_hechos_con_su_imagen(proyecto_tmp):
    carpeta = _pose(proyecto_tmp)
    with Image.open(carpeta / "ojos_cerrados.png") as o:
        assert o.mode == "RGBA" and o.height < o.width


def test_regenerar_ojos_actualiza_el_ancla_y_el_parche(proyecto_tmp):
    carpeta = _pose(proyecto_tmp)
    regenerar_ojos(carpeta, (300, 150, 80))
    cfg = yaml.safe_load((carpeta / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["anclas"]["ojos"]["x"] == 300 and cfg["anclas"]["ojos"]["ancho"] == 80
    with Image.open(carpeta / "ojos_cerrados.png") as o:
        assert o.size == (80, 32)


def test_regenerar_sin_ancla_nueva_usa_la_de_la_config(proyecto_tmp):
    carpeta = _pose(proyecto_tmp)
    regenerar_ojos(carpeta)
    assert (carpeta / "ojos_cerrados.png").is_file()
