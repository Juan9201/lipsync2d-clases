"""Ojos cerrados de prueba generados desde la imagen de la pose (hasta tener los definitivos)."""
from pathlib import Path
from typing import Optional, Tuple

import yaml
from PIL import Image

from src.biblioteca.placeholders import crear_ojos_desde_imagen
from src.errores import AssetInvalido


def _imagen_base(carpeta_pose: Path) -> Path:
    for nombre in ("base_16x9.png", "original.png"):
        if (carpeta_pose / nombre).is_file():
            return carpeta_pose / nombre
    raise AssetInvalido(f"No se encontró la imagen de la pose en {carpeta_pose}",
                        "Importa la imagen con `python -m src.biblioteca importar`")


def regenerar_ojos(carpeta_pose: Path, ojos: Optional[Tuple[float, ...]] = None) -> Path:
    """Rehace ojos_cerrados.png con el ancla de ojos de config.yaml (o con la nueva `ojos`, que
    además se guarda en la config)."""
    carpeta_pose = Path(carpeta_pose)
    cfg_ruta = carpeta_pose / "config.yaml"
    if not cfg_ruta.is_file():
        raise AssetInvalido(f"No se encontró config.yaml en {carpeta_pose}", "Prepara la pose primero")
    cfg = yaml.safe_load(cfg_ruta.read_text(encoding="utf-8"))
    if ojos is not None:
        x, y, ancho, *resto = ojos
        cfg["anclas"]["ojos"] = {"x": x, "y": y, "ancho": ancho, "angulo": resto[0] if resto else 0.0}
        cfg_ruta.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    a = cfg["anclas"]["ojos"]
    with Image.open(_imagen_base(carpeta_pose)) as im:
        return crear_ojos_desde_imagen(im, a["x"], a["y"], max(int(a["ancho"]), 8), carpeta_pose / "ojos_cerrados.png")
