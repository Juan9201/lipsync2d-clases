"""El personaje con varias poses (FR-050, FR-059): una sola capa que, en cada frame, dibuja la pose
de la toma activa (cuerpo, parpadeo y boca) con la cabeza alineada a la de la pose de referencia.

Cada pose carga sus imágenes la primera vez que se usa y se guarda en una memoria acotada (las
poses de una clase son pocas, pero un lote largo no debe acumular las 43 en cada trabajador, P3)."""
from collections import OrderedDict
from typing import Dict, Optional, Tuple

from PIL import Image

from src.alineacion import centro_cabeza, desplazamiento_alineacion
from src.biblioteca.modelos import Pose
from src.errores import AssetInvalido
from src.layers.base import CapaRGBA, ContextoFrame
from src.layers.camara import Ventana
from src.layers.concretas import AnclasEstaticas, BocaLayer, CuerpoLayer, OjosLayer


class PersonajeLayer:
    def __init__(self, poses: Dict[str, Pose], ventana: Ventana, salida: Tuple[int, int],
                 alinear: bool = True, referencia: Optional[str] = None, max_poses_en_memoria: int = 12):
        if not poses:
            raise AssetInvalido("No hay ninguna pose para dibujar al personaje", "Indica al menos una pose")
        lienzos = {p.lienzo for p in poses.values()}
        if len(lienzos) > 1:
            raise AssetInvalido(
                "Las poses de una clase deben tener el mismo lienzo, pero hay varios: "
                + ", ".join(f"{w}x{h}" for w, h in sorted(lienzos)),
                "Genera todas las poses con el mismo tamaño de imagen (por ejemplo 3840x2160)")
        self._poses = dict(poses)
        self._ventana, self._salida, self._alinear = ventana, salida, alinear
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

    def _conjunto(self, pose_id: str):
        if pose_id in self._conjuntos:
            self._conjuntos.move_to_end(pose_id)
            return self._conjuntos[pose_id]
        pose = self._poses[pose_id]
        off = desplazamiento_alineacion(self._pelo(pose_id), self._pelo_ref) if self._alinear else (0.0, 0.0)
        anclas = AnclasEstaticas(pose)
        conjunto = (CuerpoLayer(pose, self._ventana, self._salida, off),
                    OjosLayer(pose, anclas, self._ventana, self._salida, off),
                    BocaLayer(pose, anclas, self._ventana, self._salida, off))
        self._conjuntos[pose_id] = conjunto
        while len(self._conjuntos) > self._max:
            self._conjuntos.popitem(last=False)
        return conjunto

    @property
    def poses_en_memoria(self) -> int:
        return len(self._conjuntos)

    # ---- BaseLayer ----
    def renderizar(self, ctx: ContextoFrame):
        pose_id = ctx.toma.pose if ctx.toma is not None else self._primera
        if pose_id not in self._poses:
            raise AssetInvalido(
                f"La toma pide la pose «{pose_id}», que no está cargada para esta clase",
                "Revisa el nombre de la pose; las disponibles son: " + ", ".join(sorted(self._poses)))
        partes = [capa.renderizar(ctx) for capa in self._conjunto(pose_id)]
        return [c for c in partes if c is not None]
