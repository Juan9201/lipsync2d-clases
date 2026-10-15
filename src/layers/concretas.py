"""Capas concretas (FR-030): fondo del escenario, cuerpo de la pose, ojos y boca.
Los recursos estáticos se preparan una vez (el render no vuelve a escalar cada frame).

Movimiento (US3): la respiración escala la figura respecto a un pivote en el borde inferior
(a la altura de la cabeza) y el movimiento leve la desplaza; cuerpo, ojos y boca usan la misma
transformación y el mismo redondeo, así que la boca no se desliza sobre la cara."""
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

from src.biblioteca.modelos import Anclas, Pose
from src.biblioteca.validacion import VISEMAS, carpeta_fuente_bocas, carpeta_fuente_ojos
from src.layers.base import CapaRGBA, ContextoFrame
from src.layers.camara import Ventana

PASO_ESCALA = 0.0005       # la respiración se cuantiza en pasos de 0,05 % (≈ 21 niveles en ±0,5 %)
MARGEN_MOV = 12            # píxeles de relleno por lado para que el movimiento no muestre bordes


def cuantizar_escala(escala: float) -> float:
    return 1.0 + round((escala - 1.0) / PASO_ESCALA) * PASO_ESCALA


def desplazamiento_px(ctx: ContextoFrame, escala_salida: float) -> Tuple[int, int]:
    """Desplazamiento entero en píxeles de salida (el mismo para cuerpo, ojos y boca)."""
    return round(ctx.dx * escala_salida), round(ctx.dy * escala_salida)


class AnclasEstaticas:
    """Proveedor de anclas fijas leídas de config.yaml. En la Fase 2 se sustituye por uno
    por frame sin tocar el compositor (P7)."""

    def __init__(self, pose: Pose):
        self._anclas = pose.anclas

    def anclas(self, n_frame: int, pose: str) -> Anclas:
        return self._anclas


def _recortar_y_escalar(img: Image.Image, ventana: Ventana, lienzo: Tuple[int, int],
                        salida: Tuple[int, int]) -> Image.Image:
    """Recorta `ventana` (en coordenadas de lienzo) de `img`, sea cual sea su tamaño, y la
    lleva a `salida`."""
    sx, sy = img.width / lienzo[0], img.height / lienzo[1]
    caja = (ventana.x0 * sx, ventana.y0 * sy, (ventana.x0 + ventana.w) * sx, (ventana.y0 + ventana.h) * sy)
    return img.resize(salida, Image.LANCZOS, box=caja)


class FondoLayer:
    def __init__(self, ruta_fondo: Optional[Path], ventana: Ventana, lienzo: Tuple[int, int],
                 salida: Tuple[int, int], desenfoque: float = 0.0):
        self._capa: Optional[CapaRGBA] = None
        if ruta_fondo is not None:
            with Image.open(ruta_fondo) as im:
                fondo = _recortar_y_escalar(im.convert("RGB"), ventana, lienzo, salida)
            if desenfoque > 0:
                fondo = fondo.filter(ImageFilter.GaussianBlur(desenfoque))
            self._capa = CapaRGBA(fondo.convert("RGBA"), 0, 0)

    def renderizar(self, ctx: ContextoFrame) -> Optional[CapaRGBA]:
        return self._capa


class CuerpoLayer:
    def __init__(self, pose: Pose, ventana: Ventana, salida: Tuple[int, int]):
        with Image.open(pose.ruta / "cuerpo.png") as im:
            cuerpo = _recortar_y_escalar(im.convert("RGBA"), ventana, pose.lienzo, salida)
        self._capa = CapaRGBA(cuerpo, 0, 0)
        self._esc = ventana.escala(salida[0])
        self._variantes: Dict[int, Image.Image] = {}
        mov = pose.movimiento
        self._con_movimiento = mov.respiracion_escala > 0 or mov.cabeza_px > 0
        if self._con_movimiento:
            # Relleno por replicación de bordes: si el personaje toca el borde del encuadre (p. ej.
            # piernas cortadas), al moverlo no aparece un hueco.
            relleno = np.pad(np.asarray(cuerpo), ((MARGEN_MOV,) * 2, (MARGEN_MOV,) * 2, (0, 0)), mode="edge")
            self._relleno = Image.fromarray(relleno, "RGBA")
            self._px = (pose.anclas.cabeza.x - ventana.x0) * self._esc + MARGEN_MOV
            self._py = salida[1] + MARGEN_MOV                    # pivote en el borde inferior

    def _variante(self, nivel: int) -> Image.Image:
        if nivel not in self._variantes:
            s = 1.0 + nivel * PASO_ESCALA
            datos = (1 / s, 0, self._px * (1 - 1 / s), 0, 1 / s, self._py * (1 - 1 / s))
            self._variantes[nivel] = self._relleno.transform(self._relleno.size, Image.AFFINE, datos,
                                                             Image.BILINEAR)
        return self._variantes[nivel]

    def renderizar(self, ctx: ContextoFrame) -> Optional[CapaRGBA]:
        nivel = round((ctx.escala - 1.0) / PASO_ESCALA)
        ox, oy = desplazamiento_px(ctx, self._esc)
        if not self._con_movimiento or (nivel == 0 and ox == 0 and oy == 0):
            return self._capa
        img = self._relleno if nivel == 0 else self._variante(nivel)
        return CapaRGBA(img, -MARGEN_MOV + ox, -MARGEN_MOV + oy)


class _SpriteLayer:
    """Base de las capas de boca y ojos: un sprite escalado y girado sobre un ancla."""

    def __init__(self, pose: Pose, proveedor, ventana: Ventana, salida: Tuple[int, int]):
        self._pose = pose
        self._prov = proveedor
        self._v = ventana
        self._esc = ventana.escala(salida[0])
        self._alto = salida[1]
        self._cache: Dict[tuple, Image.Image] = {}

    def _sprite(self, clave: str, original: Image.Image, ancho_lienzo: float, angulo: float,
                escala_extra: float = 1.0) -> Image.Image:
        escala_extra = cuantizar_escala(escala_extra)
        k = (clave, round(ancho_lienzo, 2), round(angulo, 2), round(escala_extra, 4))
        if k not in self._cache:
            ancho = max(1, round(ancho_lienzo * self._esc * escala_extra))
            alto = max(1, round(original.height * ancho / original.width))
            img = original.resize((ancho, alto), Image.LANCZOS)
            if angulo:
                img = img.rotate(angulo, resample=Image.BICUBIC, expand=True)   # antihorario
            self._cache[k] = img
        return self._cache[k]

    def _colocar(self, img: Image.Image, x: float, y: float, ctx: ContextoFrame) -> CapaRGBA:
        # Misma transformación que el cuerpo: escala respecto al pivote inferior + desplazamiento
        px = (self._pose.anclas.cabeza.x - self._v.x0) * self._esc
        py = float(self._alto)
        escala = cuantizar_escala(ctx.escala)
        cx = px + ((x - self._v.x0) * self._esc - px) * escala
        cy = py + ((y - self._v.y0) * self._esc - py) * escala
        ox, oy = desplazamiento_px(ctx, self._esc)
        return CapaRGBA(img, round(cx - img.width / 2) + ox, round(cy - img.height / 2) + oy)


class BocaLayer(_SpriteLayer):
    def __init__(self, pose, proveedor, ventana, salida):
        super().__init__(pose, proveedor, ventana, salida)
        carpeta = carpeta_fuente_bocas(pose) / "bocas"
        self._bocas = {v: Image.open(carpeta / f"{v}.png").convert("RGBA") for v in VISEMAS}

    def renderizar(self, ctx: ContextoFrame) -> Optional[CapaRGBA]:
        a = self._prov.anclas(ctx.n_frame, self._pose.id).boca
        img = self._sprite("boca" + ctx.visema, self._bocas[ctx.visema], a.ancho, a.angulo, ctx.escala)
        return self._colocar(img, a.x, a.y, ctx)


class OjosLayer(_SpriteLayer):
    def __init__(self, pose, proveedor, ventana, salida):
        super().__init__(pose, proveedor, ventana, salida)
        self._ojos = Image.open(carpeta_fuente_ojos(pose) / "ojos_cerrados.png").convert("RGBA")

    def renderizar(self, ctx: ContextoFrame) -> Optional[CapaRGBA]:
        if not ctx.parpadeando:
            return None
        a = self._prov.anclas(ctx.n_frame, self._pose.id).ojos
        img = self._sprite("ojos", self._ojos, a.ancho, a.angulo, ctx.escala)
        return self._colocar(img, a.x, a.y, ctx)
