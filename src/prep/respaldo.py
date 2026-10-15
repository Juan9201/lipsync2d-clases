"""Modo de respaldo (FR-083): la imagen completa es la capa base de una toma fija; solo se
animan boca y ojos (parpadeo sí; sin respiración ni movimiento leve).
La preparación se hace una sola vez por pose (FR-084)."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from src.biblioteca.config_pose import anclas_por_defecto, escribir_config_pose
from src.biblioteca.placeholders import crear_bocas_placeholder, crear_ojos_desde_imagen
from src.prep.formato import ajustar_16_9


@dataclass
class ResultadoPrep:
    creada: bool
    avisos: List[str] = field(default_factory=list)


def _ancla(dato: Optional[Tuple[float, ...]], defecto: dict) -> dict:
    if dato is None:
        return defecto
    x, y, ancho, *resto = dato
    return {"x": x, "y": y, "ancho": ancho, "angulo": resto[0] if resto else 0.0}


def crear_pose_respaldo(imagen: Path, carpeta_pose: Path, id_pose: str,
                        boca: Optional[Tuple[float, ...]] = None,
                        ojos: Optional[Tuple[float, ...]] = None,
                        con_placeholders: bool = True, modo_formato: str = "recortar",
                        forzar: bool = False,
                        salida: Tuple[int, int] = (1280, 720)) -> ResultadoPrep:
    carpeta_pose = Path(carpeta_pose)
    if not forzar and (carpeta_pose / "cuerpo.png").is_file() and (carpeta_pose / "config.yaml").is_file():
        return ResultadoPrep(False, [f"La pose {id_pose} ya estaba preparada; no se repite "
                                     "(usa --forzar para rehacerla)"])
    with Image.open(imagen) as origen:
        r = ajustar_16_9(origen.convert("RGB"), modo_formato, salida=salida)
    avisos = list(r.avisos)
    carpeta_pose.mkdir(parents=True, exist_ok=True)
    cuerpo = r.imagen.convert("RGBA")
    cuerpo.save(carpeta_pose / "cuerpo.png")
    w, h = cuerpo.size
    defecto = anclas_por_defecto(w, h)
    anclas = {"boca": _ancla(boca, defecto["boca"]), "ojos": _ancla(ojos, defecto["ojos"]),
              "cabeza": defecto["cabeza"]}
    if boca is None or ojos is None:
        avisos.append("Anclas de boca y ojos provisionales: calibra la posición con clics "
                      "(o pásalas con --boca y --ojos)")
    escribir_config_pose(carpeta_pose, id_pose, carpeta_pose.name.split("_", 1)[-1]
                         if "_" in carpeta_pose.name else "", (w, h), anclas, respaldo=True)
    if con_placeholders:
        if not (carpeta_pose / "bocas" / "A.png").is_file():
            crear_bocas_placeholder(carpeta_pose)
        if not (carpeta_pose / "ojos_cerrados.png").is_file():
            crear_ojos_desde_imagen(r.imagen, anclas["ojos"]["x"], anclas["ojos"]["y"],
                                    max(int(anclas["ojos"]["ancho"]), 8), carpeta_pose / "ojos_cerrados.png")
        avisos.append("Se usan bocas y ojos placeholder; sustitúyelos por los definitivos "
                      "(ver assets/README.md)")
    return ResultadoPrep(True, avisos)
