"""FR-085: imagen no 16:9 -> aviso y recortar/rellenar sin deformar; baja resolución avisa sin bloquear."""
import pytest
from PIL import Image

from src.prep.formato import ajustar_16_9, es_16_9


def _imagen(w, h):
    im = Image.new("RGB", (w, h), (10, 20, 30))
    im.putpixel((10, 10), (255, 0, 0))          # marca para comprobar que no se deforma
    return im


def test_imagen_16_9_no_cambia_ni_avisa_formato():
    r = ajustar_16_9(_imagen(1920, 1080), "recortar", salida=(1280, 720))
    assert r.imagen.size == (1920, 1080) and not r.modificada and r.avisos == []


def test_4_3_recortar_queda_16_9_sin_deformar():
    r = ajustar_16_9(_imagen(400, 300), "recortar", salida=(100, 50))
    assert r.modificada and es_16_9(*r.imagen.size)
    assert r.imagen.size == (400, 225)
    assert any("no es 16:9" in a for a in r.avisos)


def test_recortar_imagen_demasiado_ancha_usa_el_foco():
    im = Image.new("RGB", (3000, 1000), (0, 0, 0))
    im.putpixel((2900, 500), (255, 255, 255))
    r = ajustar_16_9(im, "recortar", foco_x=2800, salida=(100, 50))
    assert es_16_9(*r.imagen.size)
    xs = [x for x in range(r.imagen.width) if r.imagen.getpixel((x, 500)) == (255, 255, 255)]
    assert xs, "el recorte centrado en el foco debe conservar el píxel marcado"


def test_4_3_rellenar_conserva_la_imagen_original_intacta():
    r = ajustar_16_9(_imagen(400, 300), "rellenar", salida=(100, 50))
    assert es_16_9(*r.imagen.size) and r.imagen.size == (534, 300)
    x0 = (534 - 400) // 2
    assert r.imagen.getpixel((x0 + 10, 10)) == (255, 0, 0)       # sin deformación
    assert r.imagen.getpixel((x0 + 100, 100)) == (10, 20, 30)


def test_baja_resolucion_avisa_sin_bloquear():
    r = ajustar_16_9(_imagen(640, 360), "recortar", salida=(1280, 720))
    assert r.imagen.size == (640, 360)
    assert any("menor que la salida" in a for a in r.avisos)


def test_modo_invalido():
    with pytest.raises(ValueError):
        ajustar_16_9(_imagen(400, 300), "estirar")
