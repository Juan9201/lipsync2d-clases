"""Acceso al entorno aislado de preparación (.venv-prep): segmentación e inpainting corren
en un proceso aparte con sus propias dependencias (rembg, PyTorch), para no cargar el
núcleo de render ni arriesgar conflictos de versiones (P8)."""
import os
import subprocess
from pathlib import Path
from typing import List

from src import rutas
from src.audio import SIN_VENTANA
from src.errores import EntornoIncompleto, ErrorAccionable

TRABAJADOR = Path(__file__).with_name("_trabajador.py")


def python_prep(raiz: Path = rutas.RAIZ) -> Path:
    py = Path(raiz) / ".venv-prep" / "Scripts" / "python.exe"
    if not py.is_file():
        raise EntornoIncompleto("Falta el grupo de preparación de assets (.venv-prep)",
                                "Ejecuta .\\instalar.ps1 -Preparacion")
    return py


def modelo_lama(raiz: Path = rutas.RAIZ) -> Path:
    return Path(raiz) / "modelos" / "prep" / "torch" / "hub" / "checkpoints" / "big-lama.pt"


def ejecutar_trabajador(args: List[str], raiz: Path = rutas.RAIZ, timeout_s: int = 1800) -> None:
    py = python_prep(raiz)
    entorno = dict(os.environ,
                   U2NET_HOME=str(Path(raiz) / "modelos" / "prep" / "rembg"),   # modelos dentro del proyecto
                   TORCH_HOME=str(Path(raiz) / "modelos" / "prep" / "torch"),
                   LAMA_MODEL=str(modelo_lama(raiz)),
                   PYTHONUTF8="1", PYTHONWARNINGS="ignore")
    try:
        r = subprocess.run([str(py), str(TRABAJADOR), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=entorno, timeout=timeout_s,
                           creationflags=SIN_VENTANA)
    except subprocess.TimeoutExpired as exc:
        raise ErrorAccionable(f"La preparación tardó más de {timeout_s // 60} min y se canceló",
                              "Prueba con una imagen más pequeña o revisa que el equipo no esté saturado") from exc
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout or "sin detalle").strip().splitlines()[-1][:300]
        raise ErrorAccionable(f"La preparación de la imagen falló ({detalle})",
                              "Comprueba que los modelos estén instalados con .\\instalar.ps1 -Preparacion")
