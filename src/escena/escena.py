"""La escena con capas como capa de render: pared + fondo trasero, el personaje (con su boca y sus ojos, por la misma ruta de siempre)
iluminado por las luces de la escena, y el frente (mesa, objetos) que lo tapa.

La boca y los parpadeos no se pueden descolocar: el personaje se dibuja con PersonajeLayer, que recorta cuerpo, ojos y boca con UNA
sola ventana. Esta capa solo calcula esa ventana para cada plano, a partir de dónde se coloca la cabeza y de qué tamaño."""
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

from src.biblioteca.modelos import Pose
from src.errores import AssetInvalido
from src.escena import config as cfgmod
from src.escena.luz import aplicar_luz, mapas_de_luz
from src.layers.base import CapaRGBA, ContextoFrame
from src.layers.camara import Ventana
from src.layers.fondo_video import FondoVideoLayer
from src.layers.personaje import PersonajeLayer
from src.timeline import Toma

SUAVIDAD_ESCENA = 90.0           # píxeles de la escena para suavizar la silueta en el relieve falso de la luz
RAMPA_MESA = 250.0               # alcance (px de la escena) de la sombra de la mesa sobre el personaje
_ACTIVOS: "OrderedDict[tuple, ActivosEscena]" = OrderedDict()
_CERROJO = threading.Lock()


class ActivosEscena:
    """Las imágenes de la escena (pesadas), cargadas una vez: fondo trasero, frente y la sombra bajo la mesa."""

    def __init__(self, carpeta: Path):
        fondo, frente = cfgmod.archivos_de_capas(carpeta)
        if fondo is None or frente is None:
            raise AssetInvalido(f"El escenario {Path(carpeta).name} necesita las dos capas (fondo y frente)",
                                "Sube el fondo trasero y el frente con transparencia en la pestaña Escenarios")
        self.carpeta, self.ruta_fondo = Path(carpeta), fondo
        self.es_video = fondo.suffix.lower() == ".mp4"
        self.lienzo = cfgmod.lienzo_de(carpeta)
        with Image.open(frente) as im:
            self.frente = im.convert("RGBA")
        if self.frente.size != self.lienzo:
            raise AssetInvalido(f"El frente mide {self.frente.size[0]}x{self.frente.size[1]} y el fondo {self.lienzo[0]}x{self.lienzo[1]}",
                                "Las dos capas deben tener exactamente el mismo tamaño y estar alineadas")
        self.fondo: Optional[Image.Image] = None
        if not self.es_video:
            with Image.open(fondo) as im:
                self.fondo = im.convert("RGBA")
            if self.fondo.size != self.lienzo:
                raise AssetInvalido(f"El fondo mide {self.fondo.size[0]}x{self.fondo.size[1]} y el frente {self.lienzo[0]}x{self.lienzo[1]}",
                                    "Las dos capas deben tener exactamente el mismo tamaño y estar alineadas")
        self.frente_total = self._frente_con_hueco()

    def _frente_con_hueco(self) -> Image.Image:
        """El frente más una zona oscura bajo el tablero, entre las patas: el personaje está sentado y sus piernas no se ven."""
        sw, sh = self.lienzo
        a = np.asarray(self.frente, dtype=np.float32)
        rgb, alfa = a[..., :3], a[..., 3]
        madera = (alfa > 200) & (rgb[..., 0] > rgb[..., 2] + 40) & (rgb[..., 0] > 120) & (rgb[..., 1] > 60)
        madera[: int(sh * 0.55)] = False
        relleno = np.zeros((sh, sw), bool)
        xs = np.where(madera.any(0))[0]
        if len(xs):
            for x in range(int(xs.min()), int(xs.max()) + 1):
                filas = np.where(madera[:, x])[0]
                if len(filas):
                    relleno[filas.max() + 1:, x] = True
        relleno &= alfa < 10
        yy = np.mgrid[0:sh, 0:sw][0]
        t = np.clip((yy - sh * 0.79) / (sh * 0.21), 0, 1)
        sombra = np.zeros((sh, sw, 4), np.uint8)
        sombra[..., 0], sombra[..., 1], sombra[..., 2] = (22 - 14 * t), (28 - 18 * t), (30 - 20 * t)
        sombra[..., 3] = np.asarray(Image.fromarray((relleno * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0)))
        total = Image.fromarray(sombra, "RGBA")
        total.alpha_composite(self.frente)
        return total


def activos_de(carpeta: Path) -> ActivosEscena:
    """Cache de las imágenes pesadas por carpeta y fecha de los archivos (el editor pide la escena muchas veces)."""
    carpeta = Path(carpeta)
    fondo, frente = cfgmod.archivos_de_capas(carpeta)
    clave = (str(carpeta), fondo.stat().st_mtime if fondo else 0, frente.stat().st_mtime if frente else 0)
    with _CERROJO:
        if clave not in _ACTIVOS:
            _ACTIVOS[clave] = ActivosEscena(carpeta)
            while len(_ACTIVOS) > 3:
                _ACTIVOS.popitem(last=False)
        _ACTIVOS.move_to_end(clave)
        return _ACTIVOS[clave]


def ventana_de_plano(plano: str, cabeza: Tuple[float, float], lienzo: Tuple[int, int], pose_ref: Pose) -> Ventana:
    """La cámara virtual sobre la escena: igual que en las poses (alto relativo y altura de la cabeza en el cuadro)."""
    sw, sh = lienzo
    cfg = pose_ref.planos[plano]
    h = cfg.alto_relativo * sh
    w = min(h * 16 / 9, sw)
    h = w * 9 / 16
    return Ventana(min(max(cabeza[0] - w / 2, 0), sw - w), min(max(cabeza[1] - cfg.centro_y_relativo * h, 0), sh - h), w, h)


class EscenaLayer:
    """BaseLayer: devuelve el cuadro completo (fondo, personaje con luz y frente) para `ctx.toma.plano`."""

    def __init__(self, carpeta: Path, config: dict, poses: Dict[str, Pose], salida: Tuple[int, int] = (1280, 720),
                 alinear: bool = True, referencia: Optional[str] = None, fps: int = 25, cache_dir: Optional[Path] = None,
                 activos: Optional[ActivosEscena] = None, planos: Optional[list] = None):
        self.carpeta, self.cfg, self.salida, self.fps = Path(carpeta), config, salida, fps
        self.activos = activos or activos_de(carpeta)
        self.poses = dict(poses)
        self._ref = self.poses[referencia] if referencia else next(iter(self.poses.values()))
        pj = config["personaje"]
        self._esc = float(pj["escala"])
        self._cabeza = tuple(pj["cabeza"])
        self._ajustes = pj.get("ajustes") or {}
        sw, sh = self.activos.lienzo
        # el lienzo de la pose (p) se lleva a la escena (q) con q = escala * p + t, de modo que la cabeza de referencia caiga en `cabeza`
        self._t = (self._cabeza[0] - self._esc * self._ref.anclas.cabeza.x, self._cabeza[1] - self._esc * self._ref.anclas.cabeza.y)
        self._planos = list(planos or ["PL1", "PL2", "PL3", "PL4", "PL5", "PL6"])
        self._v_escena = {pl: ventana_de_plano(pl, self._cabeza, (sw, sh), self._ref) for pl in self._planos}
        self._personaje = PersonajeLayer(self.poses, self._ventana_de_pose, salida, alinear=alinear, referencia=referencia)
        self._base: Dict[str, Image.Image] = {}
        self._delante: Dict[str, Image.Image] = {}
        self._mapas: "OrderedDict[tuple, tuple]" = OrderedDict()
        self._video: Optional[FondoVideoLayer] = None
        if self.activos.es_video:
            self._video = FondoVideoLayer(self.activos.ruta_fondo, self._v_escena[self._planos[0]], self.activos.lienzo, salida, fps,
                                          cache_dir=cache_dir, ventanas=self._v_escena)

    # ---- geometría ----
    def ventana_escena(self, plano: str) -> Ventana:
        return self._v_escena[plano]

    def _ventana_de_pose(self, pose_id: str, plano: str) -> Ventana:
        """La ventana del plano en coordenadas del lienzo de la pose (con el ajuste fino de esa pose, si lo tiene)."""
        v = self._v_escena[plano]
        a = self._ajustes.get(pose_id) or {}
        tx, ty = self._t[0] + float(a.get("dx", 0)), self._t[1] + float(a.get("dy", 0))
        return Ventana((v.x0 - tx) / self._esc, (v.y0 - ty) / self._esc, v.w / self._esc, v.h / self._esc)

    def a_pantalla(self, x: float, y: float, plano: str) -> Tuple[float, float]:
        """Un punto de la escena en píxeles del cuadro de salida (para dibujar guías en el editor)."""
        v = self._v_escena[plano]
        k = self.salida[0] / v.w
        return (x - v.x0) * k, (y - v.y0) * k

    # ---- capas estáticas por plano ----
    def _recorte(self, img: Image.Image, plano: str) -> Image.Image:
        v = self._v_escena[plano]
        return img.resize(self.salida, Image.LANCZOS, box=(v.x0, v.y0, v.x0 + v.w, v.y0 + v.h))

    def _pared(self) -> Image.Image:
        w, h = self.salida
        c = self.cfg["pared"]
        y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        x = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
        arriba, abajo = np.array(c["arriba"], np.float32), np.array(c["abajo"], np.float32)
        arr = (arriba * (1 - y) + abajo * y) * (1 - 0.18 * (((x - 0.5) * 1.5) ** 2 + ((y - 0.45) * 1.2) ** 2))
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    def _base_de(self, plano: str, n_frame: int) -> Image.Image:
        if self._video is not None:
            ctx = ContextoFrame(n_frame, n_frame / self.fps, self.salida, Toma(0, "E?", next(iter(self.poses)), plano), "X", False, 1.0, 0.0, 0.0)
            return self._video.renderizar(ctx).imagen.copy()
        if plano not in self._base:
            b = self._pared()
            b.alpha_composite(self._recorte(self.activos.fondo, plano))
            self._base[plano] = b
        return self._base[plano].copy()

    def _delante_de(self, plano: str) -> Image.Image:
        if plano not in self._delante:
            self._delante[plano] = self._recorte(self.activos.frente_total, plano)
        return self._delante[plano]

    # ---- el personaje ----
    def _personaje_rgba(self, ctx: ContextoFrame) -> Image.Image:
        w, h = self.salida
        lienzo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for c in self._personaje.renderizar(ctx):
            xa, ya = max(c.x, 0), max(c.y, 0)
            lienzo.alpha_composite(c.imagen.crop((xa - c.x, ya - c.y, min(c.x + c.imagen.width, w) - c.x, min(c.y + c.imagen.height, h) - c.y)),
                                   dest=(xa, ya))
        return lienzo

    def _mapas_de(self, pose_id: str, plano: str):
        clave = (pose_id, plano)
        if clave not in self._mapas:
            v = self._v_escena[plano]
            k = self.salida[0] / v.w
            luces = [{**L, "pos": ((L["pos"][0] - v.x0) * k, (L["pos"][1] - v.y0) * k), "alcance": L["alcance"] * k, "altura": L["altura"] * k}
                     for L in self.cfg["luz"]["luces"]]
            fijo = self._personaje_rgba(ContextoFrame(0, 0.0, self.salida, Toma(0, "E?", pose_id, plano), "X", False, 1.0, 0.0, 0.0))
            mult, suma = mapas_de_luz(fijo, luces, self.cfg["luz"]["ambiente"], (self.cfg["mesa"]["y"] - v.y0) * k, RAMPA_MESA * k,
                                      SUAVIDAD_ESCENA * k)
            ys, xs = np.where(np.asarray(fijo)[..., 3] > 0)
            caja = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else (0, 0, 1, 1)
            self._mapas[clave] = (mult, suma, caja)
            while len(self._mapas) > 24:
                self._mapas.popitem(last=False)
        return self._mapas[clave]

    # ---- BaseLayer ----
    def componer(self, ctx: ContextoFrame, con_luz: Optional[bool] = None) -> Image.Image:
        toma = ctx.toma
        if toma is None:
            raise AssetInvalido("La escena necesita saber la pose y el plano de la toma", "Indica una toma")
        if toma.plano not in self._v_escena:
            raise AssetInvalido(f"La escena no tiene el plano «{toma.plano}»", "Los planos disponibles son: " + ", ".join(self._planos))
        cuadro = self._base_de(toma.plano, ctx.n_frame)
        pj = self._personaje_rgba(ctx)
        usar_luz = self.cfg["luz"]["activa"] and bool(self.cfg["luz"]["luces"]) if con_luz is None else con_luz
        if usar_luz:
            mult, suma, (x0, y0, x1, y1) = self._mapas_de(toma.pose, toma.plano)
            cuadro.alpha_composite(aplicar_luz(pj.crop((x0, y0, x1, y1)), mult[y0:y1, x0:x1], suma[y0:y1, x0:x1]), dest=(x0, y0))
        else:
            cuadro.alpha_composite(pj)
        cuadro.alpha_composite(self._delante_de(toma.plano))
        return cuadro

    def renderizar(self, ctx: ContextoFrame) -> CapaRGBA:
        return CapaRGBA(self.componer(ctx), 0, 0)

    def vista(self, pose_id: str, plano: str, visema: str = "X", ojos: str = "abierto", con_luz: Optional[bool] = None) -> Image.Image:
        """Un cuadro fijo para el editor: la pose, el plano, la forma de boca y el estado de los ojos que se pidan."""
        ctx = ContextoFrame(0, 0.0, self.salida, Toma(0, "E?", pose_id, plano), visema, ojos != "abierto", 1.0, 0.0, 0.0, ojos)
        return self.componer(ctx, con_luz).convert("RGB")

    def cerrar(self) -> None:
        if self._video is not None:
            self._video.cerrar()
