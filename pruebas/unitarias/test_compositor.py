"""FR-030, P7: el compositor solo conoce BaseLayer, no capas concretas."""
from PIL import Image

from src.compositor import Compositor
from src.layers.base import CapaRGBA, ContextoFrame


class CapaCuadrado:
    """Capa falsa: dibuja un cuadrado de color en una posición."""

    def __init__(self, color, x, y, lado=10):
        self.color, self.x, self.y, self.lado = color, x, y, lado
        self.llamadas = []

    def renderizar(self, ctx: ContextoFrame):
        self.llamadas.append(ctx.n_frame)
        return CapaRGBA(Image.new("RGBA", (self.lado, self.lado), self.color), self.x, self.y)


class CapaVacia:
    def renderizar(self, ctx):
        return None


def _ctx(n=0):
    return ContextoFrame(n_frame=n, t=n / 25, salida=(64, 36), toma=None, visema="X",
                         parpadeando=False, escala=1.0, dx=0.0, dy=0.0)


def test_orden_de_capas_la_ultima_queda_arriba():
    roja = CapaCuadrado((255, 0, 0, 255), 5, 5, 20)
    azul = CapaCuadrado((0, 0, 255, 255), 10, 10, 20)
    comp = Compositor([roja, azul], salida=(64, 36))
    frame = comp.componer(_ctx())
    assert frame.size == (64, 36) and frame.mode == "RGB"
    assert frame.getpixel((7, 7)) == (255, 0, 0)       # solo roja
    assert frame.getpixel((15, 15)) == (0, 0, 255)     # azul encima


def test_capa_que_devuelve_none_se_ignora():
    comp = Compositor([CapaVacia(), CapaCuadrado((0, 255, 0, 255), 0, 0, 4)], salida=(64, 36))
    assert comp.componer(_ctx()).getpixel((1, 1)) == (0, 255, 0)


def test_capa_parcialmente_fuera_del_lienzo_se_recorta():
    comp = Compositor([CapaCuadrado((255, 255, 0, 255), 60, 30, 20)], salida=(64, 36))
    frame = comp.componer(_ctx())
    assert frame.getpixel((63, 35)) == (255, 255, 0)


def test_transparencia_se_mezcla():
    capa = CapaCuadrado((255, 0, 0, 128), 0, 0, 8)
    comp = Compositor([capa], salida=(64, 36), color_fondo=(0, 0, 0))
    r, g, b = comp.componer(_ctx()).getpixel((2, 2))
    assert 120 <= r <= 135 and g == 0 and b == 0


def test_el_contexto_llega_a_cada_capa():
    capa = CapaCuadrado((1, 2, 3, 255), 0, 0, 2)
    comp = Compositor([capa], salida=(64, 36))
    comp.componer(_ctx(7))
    comp.componer(_ctx(8))
    assert capa.llamadas == [7, 8]
