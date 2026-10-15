"""Inpainting (FR-081): reconstruye el fondo donde estaba el personaje para obtener un
escenario limpio. LaMa corre en CPU dentro de .venv-prep (16 s para una imagen de 2048x1152)."""
from pathlib import Path

from src import rutas
from src.errores import AssetInvalido
from src.prep.entorno_prep import ejecutar_trabajador, modelo_lama, python_prep


def crear_escenario(original: Path, mascara: Path, destino: Path, margen_px: int = 15,
                    raiz: Path = rutas.RAIZ) -> Path:
    """`mascara` marca al personaje (blanco). Se dilata `margen_px` para tapar el borde."""
    original, mascara, destino = Path(original), Path(mascara), Path(destino)
    if not original.is_file():
        raise AssetInvalido(f"No se encontró la imagen original {original}",
                            "Importa la imagen con `python -m src.biblioteca importar`")
    if not mascara.is_file():
        raise AssetInvalido(f"No se encontró la máscara del personaje ({mascara})",
                            "Genera la pose primero (`python -m src.prep pose P1`) para obtener mascara.png")
    python_prep(raiz)
    if not modelo_lama(raiz).is_file():
        from src.errores import EntornoIncompleto
        raise EntornoIncompleto("Falta el modelo de inpainting LaMa", "Ejecuta .\\instalar.ps1 -Preparacion")
    destino.parent.mkdir(parents=True, exist_ok=True)
    ejecutar_trabajador(["inpaint", str(original), str(mascara), str(destino), "--margen", str(margen_px)], raiz)
    return destino
