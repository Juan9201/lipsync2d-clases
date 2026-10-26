"""«Actualizar poses»: pasa a `personajes/<p>/poses/<pose>/cuerpo.png` las imágenes que cambiaste en `Temp Real Assest Testing/Torso Organizado/`.

El render solo lee `personajes/…`; la carpeta Torso Organizado es un área de preparación. Una imagen corregida con el mismo nombre se copia sola
si la cara quedó donde estaba (las bocas y el parpadeo calibrados siguen valiendo). Si la cara se movió, no se toca nada: hay que recalibrar.
Antes de pisar nada se guarda la imagen anterior en `respaldo_poses/<fecha>_actualizar/`.
"""
import hashlib
import shutil
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import yaml
from PIL import Image

from src.biblioteca.modelos import _NOMBRE_POSE_V3

ORIGEN = Path("Temp Real Assest Testing") / "Torso Organizado"
TOLERANCIA_CARA_PX = 2                    # la cara puede variar hasta esto sin invalidar la calibración de la boca
BUSQUEDA_PX = 12


def _md5(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def _desplazamiento_cara(actual: Path, nueva: Path, boca: Dict[str, float]):
    """(dx, dy, error) de la cara de `nueva` respecto a `actual`, buscando alrededor de la boca A; None si no tienen el mismo tamaño."""
    a, b = Image.open(actual).convert("L"), Image.open(nueva).convert("L")
    if a.size != b.size:
        return None
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    cx, cy = int(boca["x"]), int(boca["y"])
    y0, y1, x0, x1 = cy - 230, cy + 80, cx - 150, cx + 150
    if y0 - BUSQUEDA_PX < 0 or x0 - BUSQUEDA_PX < 0 or y1 + BUSQUEDA_PX > a.shape[0] or x1 + BUSQUEDA_PX > a.shape[1]:
        return None
    plantilla = a[y0:y1:2, x0:x1:2]
    mejor = (1e18, 0, 0)
    for dy in range(-BUSQUEDA_PX, BUSQUEDA_PX + 1):
        for dx in range(-BUSQUEDA_PX, BUSQUEDA_PX + 1):
            e = float(np.abs(b[y0 + dy:y1 + dy:2, x0 + dx:x1 + dx:2] - plantilla).mean())
            if e < mejor[0]:
                mejor = (e, dx, dy)
    return mejor[1], mejor[2], mejor[0]


def revisar(raiz: Path, personaje: str = "profesor") -> List[dict]:
    """Qué imágenes de Torso Organizado difieren de las poses importadas. Cada elemento: pose, estado y detalle.
    Estados: «actualizable» (se copia sola), «cara_movida» (hay que recalibrar), «nueva» (no hay pose con ese nombre) y «nombre_invalido»."""
    raiz = Path(raiz)
    fuente, poses = raiz / ORIGEN, raiz / "personajes" / personaje / "poses"
    salida: List[dict] = []
    if not fuente.is_dir():
        return salida
    for carpeta in sorted(d for d in fuente.iterdir() if d.is_dir() and "blink" not in d.name.lower() and not d.name.startswith(("_", "."))):
        for img in sorted(carpeta.glob("*.png")):
            pose = img.stem
            if not _NOMBRE_POSE_V3.match(pose):
                salida.append({"pose": pose, "estado": "nombre_invalido", "origen": carpeta.name,
                               "detalle": "el nombre no sigue «vista_gesto_NN» (por ejemplo frontal_contar_03)"})
                continue
            destino = poses / pose
            if not destino.is_dir():
                salida.append({"pose": pose, "estado": "nueva", "origen": carpeta.name,
                               "detalle": "aún no es una pose: impórtala y calibra su boca en el editor"})
                continue
            if _md5(img) == _md5(destino / "cuerpo.png"):
                continue
            cfg = yaml.safe_load((destino / "config.yaml").read_text(encoding="utf-8")) or {}
            r = _desplazamiento_cara(destino / "cuerpo.png", img, cfg["formas"]["A"])
            if r is None:
                salida.append({"pose": pose, "estado": "cara_movida", "origen": carpeta.name,
                               "detalle": "la imagen tiene otro tamaño o la cara no se pudo comparar: hay que recalibrar"})
            elif max(abs(r[0]), abs(r[1])) > TOLERANCIA_CARA_PX:
                salida.append({"pose": pose, "estado": "cara_movida", "origen": carpeta.name,
                               "detalle": f"la cara se movió {r[0]:+d}, {r[1]:+d} px: hay que recalibrar la boca"})
            else:
                salida.append({"pose": pose, "estado": "actualizable", "origen": carpeta.name,
                               "detalle": f"la cara sigue en su sitio ({r[0]:+d}, {r[1]:+d} px): se conservan las bocas y el parpadeo"})
    return salida


def actualizar(raiz: Path, personaje: str = "profesor") -> dict:
    """Copia las imágenes «actualizables» (guardando antes las anteriores). Devuelve lo hecho y lo que queda por hacer a mano."""
    raiz = Path(raiz)
    cambios = revisar(raiz, personaje)
    hechas, pendientes = [], [c for c in cambios if c["estado"] != "actualizable"]
    por_hacer = [c for c in cambios if c["estado"] == "actualizable"]
    if por_hacer:
        respaldo = raiz / "respaldo_poses" / (time.strftime("%Y-%m-%d_%H%M%S") + "_actualizar")
        for c in por_hacer:
            destino = raiz / "personajes" / personaje / "poses" / c["pose"]
            (respaldo / c["pose"]).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destino / "cuerpo.png", respaldo / c["pose"] / "cuerpo.png")
            shutil.copyfile(raiz / ORIGEN / c["origen"] / f"{c['pose']}.png", destino / "cuerpo.png")
            hechas.append(c["pose"])
    return {"actualizadas": hechas, "pendientes": pendientes,
            "respaldo": str(respaldo) if por_hacer else ""}
