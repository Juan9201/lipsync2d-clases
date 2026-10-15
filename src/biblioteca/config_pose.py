"""Escritura del config.yaml de una pose (contrato config-pose-escenario.md)."""
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml


def anclas_por_defecto(ancho: int, alto: int) -> Dict[str, dict]:
    """Posiciones provisionales (centro de la imagen). Deben calibrarse con clics (FR-062)."""
    return {
        "boca": {"x": int(ancho * 0.5), "y": int(alto * 0.40), "ancho": int(ancho * 0.06), "angulo": 0.0},
        "ojos": {"x": int(ancho * 0.5), "y": int(alto * 0.30), "ancho": int(ancho * 0.10), "angulo": 0.0},
        "cabeza": {"x": int(ancho * 0.5), "y": int(alto * 0.30)},
    }


def escribir_config_pose(carpeta: Path, id_pose: str, nombre: str, lienzo: Tuple[int, int],
                         anclas: Optional[Dict[str, dict]] = None, respaldo: bool = False) -> Path:
    config = {
        "version": 1, "id": id_pose, "nombre": nombre, "lienzo": [int(lienzo[0]), int(lienzo[1])],
        "espejo": False, "bocas_de": None,
        "anclas": anclas or anclas_por_defecto(*lienzo),
    }
    if respaldo:
        config["respaldo"] = True
        config["movimiento"] = {"respiracion_escala": 0.0, "cabeza_px": 0.0}
    ruta = Path(carpeta) / "config.yaml"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return ruta
