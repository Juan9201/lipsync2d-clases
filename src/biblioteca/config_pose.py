"""Escritura del config.yaml de una pose (contrato config-pose-escenario.md)."""
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

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


def escribir_config_pose_v4(carpeta: Path, vista: str, gesto: str, variante: int, lienzo: Tuple[int, int],
                            formas: Dict[str, dict], espejo: bool = False, bocas_de: Optional[str] = None,
                            tipo: Optional[str] = None, cabeza: Optional[Tuple[float, float]] = None,
                            pelo: Optional[Tuple[float, float]] = None, parpadeo: Union[bool, dict, None] = False,
                            ojos_de: Optional[str] = None) -> Path:
    """config.yaml de una pose de la v3: vista, gesto, variante y calibración de boca por forma
    (x, y, s, r, m). `formas` vacío = pose importada sin calibrar."""
    carpeta = Path(carpeta)
    config = {
        "version": 4, "id": carpeta.name, "vista": vista, "gesto": gesto, "variante": int(variante),
        "lienzo": [int(lienzo[0]), int(lienzo[1])], "espejo": bool(espejo), "bocas_de": bocas_de,
        "parpadeo": parpadeo if isinstance(parpadeo, dict) else bool(parpadeo),
    }
    if tipo:
        config["tipo"] = tipo
    if ojos_de:
        config["ojos_de"] = ojos_de
    if cabeza is not None:
        config["anclas"] = {"cabeza": {"x": float(cabeza[0]), "y": float(cabeza[1])}}
    if pelo is not None:
        config["pelo"] = [round(float(pelo[0]), 2), round(float(pelo[1]), 2)]
    config["formas"] = {v: {"x": float(f["x"]), "y": float(f["y"]), "s": float(f["s"]),
                            "r": float(f.get("r", 0.0)), "m": bool(f.get("m", False))} for v, f in formas.items()}
    ruta = carpeta / "config.yaml"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return ruta
