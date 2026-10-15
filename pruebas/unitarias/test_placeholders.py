"""FR-060: bocas placeholder generadas por código, válidas sin assets del usuario."""
import hashlib

from PIL import Image

from src.biblioteca.modelos import cargar_pose
from src.biblioteca.placeholders import crear_pose_placeholder
from src.biblioteca.validacion import VISEMAS, validar_pose


def test_pose_placeholder_pasa_la_validacion(proyecto_tmp):
    carpeta = proyecto_tmp / "personajes" / "demo" / "poses" / "P1_placeholder"
    crear_pose_placeholder(carpeta, "P1", lienzo=(320, 180))
    pose = validar_pose(carpeta)
    assert pose.id == "P1" and pose.lienzo == (320, 180)
    assert 0 < pose.anclas.boca.x < 320


def test_las_nueve_bocas_son_distintas_y_del_mismo_tamano(proyecto_tmp):
    carpeta = proyecto_tmp / "personajes" / "demo" / "poses" / "P1_placeholder"
    crear_pose_placeholder(carpeta, "P1", lienzo=(320, 180))
    huellas, tamanos = set(), set()
    for v in VISEMAS:
        with Image.open(carpeta / "bocas" / f"{v}.png") as im:
            assert im.mode == "RGBA"
            tamanos.add(im.size)
            huellas.add(hashlib.md5(im.tobytes()).hexdigest())
    assert len(tamanos) == 1
    assert len(huellas) == 9


def test_config_generada_se_puede_cargar(proyecto_tmp):
    carpeta = proyecto_tmp / "personajes" / "demo" / "poses" / "P2_otra"
    crear_pose_placeholder(carpeta, "P2", lienzo=(640, 360))
    assert cargar_pose(carpeta).anclas.cabeza.y > 0


def test_ojos_cerrados_a_partir_de_la_propia_imagen(tmp_path):
    """El párpado de prueba usa el color de piel de la imagen y solo cubre los ojos (no la montura)."""
    from PIL import ImageDraw
    from src.biblioteca.placeholders import crear_ojos_desde_imagen
    cara = Image.new("RGB", (400, 200), (225, 175, 140))                       # piel
    d = ImageDraw.Draw(cara)
    for ex in (170, 230):                                                      # dos ojos azules
        d.ellipse((ex - 12, 88, ex + 12, 108), fill=(255, 255, 255))
        d.ellipse((ex - 6, 90, ex + 6, 106), fill=(60, 90, 200))
    d.rectangle((195, 95, 205, 101), fill=(30, 40, 90))                        # puente de la montura
    destino = tmp_path / "ojos_cerrados.png"
    crear_ojos_desde_imagen(cara, 200, 98, 100, destino)
    with Image.open(destino) as parche:
        assert parche.mode == "RGBA" and parche.size == (100, 40)
        izq, der, centro = (parche.getpixel((20, 20)), parche.getpixel((80, 20)), parche.getpixel((50, 20)))
        assert izq[3] > 200 and der[3] > 200                                   # cubre cada ojo
        assert centro[3] < 30                                                  # no tapa el puente
        assert abs(izq[0] - 225) < 25 and abs(izq[1] - 175) < 30 and izq[2] < 190   # color de piel, no azul
        assert parche.getpixel((2, 2))[3] == 0                                 # esquinas transparentes
