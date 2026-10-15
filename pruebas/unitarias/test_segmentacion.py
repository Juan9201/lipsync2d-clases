"""FR-080, FR-082, FR-084: segmentación del personaje, máscara editable y preparación única."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import validar_pose
from src.errores import AssetInvalido
from src.prep.segmentar import aplicar_mascara, preparar_pose_segmentada, reimportar_mascara

RAIZ = Path(__file__).resolve().parents[2]


def _original(ruta: Path, tam=(320, 180)):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", tam, (90, 140, 200))
    im.paste((240, 240, 240), (200, 20, 300, 170))
    im.save(ruta)
    return ruta


def _mascara_personaje(tam=(320, 180)):
    m = Image.new("L", tam, 0)
    m.paste(255, (200, 20, 300, 170))
    return m


def test_aplicar_mascara_pone_la_mascara_como_alfa_y_conserva_el_color():
    rgb = Image.new("RGB", (40, 20), (10, 20, 30))
    mascara = Image.new("L", (40, 20), 0)
    mascara.paste(255, (0, 0, 20, 20))
    rgba = aplicar_mascara(rgb, mascara)
    assert rgba.mode == "RGBA" and rgba.getpixel((5, 5)) == (10, 20, 30, 255)
    assert rgba.getpixel((30, 5))[3] == 0


def test_mascara_de_otro_tamano_da_error():
    with pytest.raises(AssetInvalido) as exc:
        aplicar_mascara(Image.new("RGB", (40, 20)), Image.new("L", (30, 20)))
    assert "mascara.png" in str(exc.value) and "Qué hacer" in str(exc.value)


@pytest.fixture
def pose_dir(proyecto_tmp):
    return proyecto_tmp / "personajes" / "profesor" / "poses" / "P1_profesor"


class SegmentadorFalso:
    def __init__(self):
        self.llamadas = 0

    def __call__(self, original: Path, mascara_salida: Path, modelo: str):
        self.llamadas += 1
        _mascara_personaje(Image.open(original).size).save(mascara_salida)


def test_prepara_la_pose_completa(pose_dir):
    original = _original(pose_dir / "original.png")
    seg = SegmentadorFalso()
    r = preparar_pose_segmentada(original, pose_dir, "P1", segmentador=seg)
    assert r.creada and seg.llamadas == 1
    pose = validar_pose(pose_dir)                      # cuerpo RGBA, 9 bocas, ojos, config
    assert pose.respaldo is False and pose.lienzo == (320, 180)
    with Image.open(pose_dir / "cuerpo.png") as c:
        assert c.getpixel((250, 100))[3] == 255 and c.getpixel((10, 10))[3] == 0
    assert (pose_dir / "mascara.png").is_file()        # máscara exportada para editar a mano


def test_segunda_ejecucion_no_vuelve_a_segmentar(pose_dir):
    original = _original(pose_dir / "original.png")
    seg = SegmentadorFalso()
    preparar_pose_segmentada(original, pose_dir, "P1", segmentador=seg)
    r = preparar_pose_segmentada(original, pose_dir, "P1", segmentador=seg)
    assert not r.creada and seg.llamadas == 1 and any("ya estaba preparada" in a for a in r.avisos)
    assert preparar_pose_segmentada(original, pose_dir, "P1", segmentador=seg, forzar=True).creada
    assert seg.llamadas == 2


def test_una_mascara_editada_a_mano_se_respeta(pose_dir):
    original = _original(pose_dir / "original.png")
    pose_dir.mkdir(parents=True, exist_ok=True)
    editada = _mascara_personaje()
    editada.paste(0, (200, 20, 300, 60))               # el usuario recortó la parte de arriba
    editada.save(pose_dir / "mascara.png")
    seg = SegmentadorFalso()
    preparar_pose_segmentada(original, pose_dir, "P1", segmentador=seg)
    assert seg.llamadas == 0                           # ya había máscara: no se segmenta de nuevo
    with Image.open(pose_dir / "cuerpo.png") as c:
        assert c.getpixel((250, 40))[3] == 0 and c.getpixel((250, 100))[3] == 255


def test_reimportar_mascara_regenera_el_cuerpo(pose_dir, proyecto_tmp):
    original = _original(pose_dir / "original.png")
    preparar_pose_segmentada(original, pose_dir, "P1", segmentador=SegmentadorFalso())
    editada = _mascara_personaje()
    editada.paste(0, (200, 100, 300, 170))
    ruta = proyecto_tmp / "entrada" / "mi máscara.png"
    editada.save(ruta)
    reimportar_mascara(pose_dir, ruta)
    with Image.open(pose_dir / "cuerpo.png") as c:
        assert c.getpixel((250, 140))[3] == 0 and c.getpixel((250, 60))[3] == 255
    assert np.array_equal(np.asarray(Image.open(pose_dir / "mascara.png")), np.asarray(editada))


def test_reimportar_sin_original_explica_que_hacer(pose_dir, proyecto_tmp):
    pose_dir.mkdir(parents=True)
    ruta = proyecto_tmp / "entrada" / "m.png"
    _mascara_personaje().save(ruta)
    with pytest.raises(AssetInvalido) as exc:
        reimportar_mascara(pose_dir, ruta)
    assert "original.png" in str(exc.value)


def test_imagen_no_16_9_se_ajusta_antes_de_segmentar(pose_dir):
    original = _original(pose_dir / "original.png", (300, 300))
    r = preparar_pose_segmentada(original, pose_dir, "P1", segmentador=SegmentadorFalso(), modo_formato="recortar")
    assert cargar_pose(pose_dir).lienzo == (300, 169) and any("no es 16:9" in a for a in r.avisos)


@pytest.mark.lento
@pytest.mark.integracion
def test_segmentacion_real_de_p1_coincide_con_la_referencia_revisada(proyecto_tmp):
    """FR-080: IoU >= 0.95 frente a la máscara de BiRefNet revisada a ojo en el spike S2."""
    from src.prep.entorno_prep import python_prep
    imagen = RAIZ / "Temp Real Assest Testing" / "P1_profesor.png"
    referencia = RAIZ / "pruebas" / "datos" / "p1_mascara_referencia.png"
    modelo = RAIZ / "modelos" / "prep" / "rembg" / "models" / "birefnet-general" / "birefnet-general.onnx"
    if not (imagen.exists() and modelo.exists()):
        pytest.skip("faltan la imagen real o el modelo BiRefNet")
    python_prep()
    pose_dir = proyecto_tmp / "personajes" / "profesor" / "poses" / "P1_profesor"
    preparar_pose_segmentada(imagen, pose_dir, "P1")
    obtenida = np.asarray(Image.open(pose_dir / "mascara.png")) > 127
    esperada = np.asarray(Image.open(referencia)) > 127
    iou = (obtenida & esperada).sum() / (obtenida | esperada).sum()
    assert iou >= 0.95, f"IoU {iou:.3f}"
