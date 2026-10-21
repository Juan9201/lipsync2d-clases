"""El personaje con varias poses (FR-050, FR-059): una sola capa que, en cada frame, dibuja la pose
de la toma activa (cuerpo, parpadeo y boca) con la cabeza alineada a la de la pose de referencia.

Cada pose carga sus imágenes la primera vez que se usa y se guarda en una memoria acotada (las
poses de una clase son pocas, pero un lote largo no debe acumular las 43 en cada trabajador, P3)."""
from collections import OrderedDict
from typing import Callable, Dict, List, Mapping, Optional, Tuple, Union

from PIL import Image

from src.alineacion import centro_cabeza, desplazamiento_alineacion
from src.biblioteca.modelos import Pose
from src.errores import AssetInvalido
from src.layers.base import CapaRGBA, ContextoFrame
from src.layers.camara import Ventana
from src.layers.concretas import AnclasEstaticas, BocaLayer, CuerpoLayer, OjosLayer


class PersonajeLayer:
    def __init__(self, poses: Dict[str, Pose], ventana: Union[Ventana, Mapping[str, Ventana], Callable[[str, str], Ventana]], salida: Tuple[int, int],
                 alinear: bool = True, referencia: Optional[str] = None, max_poses_en_memoria: int = 16):
        if not poses:
            raise AssetInvalido("No hay ninguna pose para dibujar al personaje", "Indica al menos una pose")
        lienzos = {p.lienzo for p in poses.values()}
        if len(lienzos) > 1:
            raise AssetInvalido(
                "Las poses de una clase deben tener el mismo lienzo, pero hay varios: "
                + ", ".join(f"{w}x{h}" for w, h in sorted(lienzos)),
                "Genera todas las poses con el mismo tamaño de imagen (por ejemplo 3840x2160)")
        self._poses = dict(poses)
        # una ventana fija, o una por plano (la cámara virtual cambia de plano en cada toma)
        # (en un escenario con capas, una función (pose, plano) -> ventana: cada pose puede llevar su propio ajuste)
        self._funcion = ventana if callable(ventana) else None
        self._ventanas = dict(ventana) if isinstance(ventana, Mapping) else None
        self._ventana = None if (self._ventanas is not None or self._funcion is not None) else ventana
        self._salida, self._alinear = salida, alinear
        self._max = max(1, max_poses_en_memoria)
        self._primera = next(iter(self._poses))
        ref_id = referencia or self._primera
        if ref_id not in self._poses:
            raise AssetInvalido(f"La pose de referencia «{ref_id}» no está entre las poses de la clase",
                                "Elige como referencia una de las poses cargadas")
        self._pelos: Dict[str, Tuple[float, float]] = {}
        self._pelo_ref = self._pelo(ref_id) if alinear else None
        self._conjuntos: "OrderedDict[str, tuple]" = OrderedDict()

    # ---- medición de la cabeza (se lee de config.yaml si ya está calculada) ----
    def _pelo(self, pose_id: str) -> Tuple[float, float]:
        if pose_id not in self._pelos:
            pose = self._poses[pose_id]
            if pose.pelo is not None:
                self._pelos[pose_id] = pose.pelo
            else:
                with Image.open(pose.ruta / "cuerpo.png") as im:
                    self._pelos[pose_id] = centro_cabeza(im)
        return self._pelos[pose_id]

    def _ventana_de(self, plano: Optional[str], pose_id: Optional[str] = None) -> Ventana:
        if self._funcion is not None:
            return self._funcion(pose_id, plano)
        if self._ventanas is None:
            return self._ventana
        if plano not in self._ventanas:
            raise AssetInvalido(f"La toma pide el plano «{plano}», que no está preparado para esta clase",
                                "Los planos disponibles son: " + ", ".join(sorted(self._ventanas)))
        return self._ventanas[plano]

    def _conjunto(self, pose_id: str, plano: Optional[str] = None):
        ventana = self._ventana_de(plano, pose_id)
        clave = pose_id if (self._ventanas is None and self._funcion is None) else f"{pose_id}|{plano}"
        if clave in self._conjuntos:
            self._conjuntos.move_to_end(clave)
            return self._conjuntos[clave]
        pose = self._poses[pose_id]
        off = desplazamiento_alineacion(self._pelo(pose_id), self._pelo_ref) if self._alinear else (0.0, 0.0)
        anclas = AnclasEstaticas(pose)
        conjunto = (CuerpoLayer(pose, ventana, self._salida, off),
                    OjosLayer(pose, anclas, ventana, self._salida, off),
                    BocaLayer(pose, anclas, ventana, self._salida, off))
        self._conjuntos[clave] = conjunto
        while len(self._conjuntos) > self._max:
            self._conjuntos.popitem(last=False)
        return conjunto

    @property
    def poses_en_memoria(self) -> int:
        return len(self._conjuntos)

    # ---- BaseLayer ----
    def _capas_de(self, pose_id: str, plano: Optional[str], ctx: ContextoFrame) -> List[CapaRGBA]:
        if pose_id not in self._poses:
            raise AssetInvalido(
                f"La toma pide la pose «{pose_id}», que no está cargada para esta clase",
                "Revisa el nombre de la pose; las disponibles son: " + ", ".join(sorted(self._poses)))
        partes = [capa.renderizar(ctx) for capa in self._conjunto(pose_id, plano)]
        return [c for c in partes if c is not None]

    def renderizar(self, ctx: ContextoFrame):
        toma = ctx.toma
        pose_id = toma.pose if toma is not None else self._primera
        plano = toma.plano if toma is not None else (next(iter(self._ventanas)) if self._ventanas else None)
        actuales = self._capas_de(pose_id, plano, ctx)
        if ctx.toma_previa is None or ctx.mezcla >= 1.0:
            return actuales
        # Mezcla entre dos poses (FR-044): la anterior completa debajo y la nueva con su opacidad por encima
        previas = self._capas_de(ctx.toma_previa.pose, plano, ctx)
        return previas + [_con_opacidad(c, ctx.mezcla) for c in actuales]


def _con_opacidad(capa: CapaRGBA, opacidad: float) -> CapaRGBA:
    img = capa.imagen.copy()
    alfa = img.getchannel("A").point(lambda v: round(v * opacidad))
    img.putalpha(alfa)
    return CapaRGBA(img, capa.x, capa.y)
