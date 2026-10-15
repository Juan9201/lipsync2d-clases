"""Verificación del entorno (FR-002): estado de cada dependencia y acción correctiva.

Uso:  python -m src.entorno          (código de salida 1 si falta algo obligatorio)
"""
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

INSTALAR = "Ejecuta .\\instalar.ps1"
INSTALAR_PREP = "Ejecuta .\\instalar.ps1 -Preparacion"


@dataclass(frozen=True)
class Dependencia:
    nombre: str
    ok: bool
    detalle: str
    accion: str
    ruta: Optional[str]   # ruta relativa al proyecto si es un archivo; None si no lo es
    requerida: bool


# (nombre, ruta relativa, requerida, acción si falta)
_ARCHIVOS = [
    ("ffmpeg", "herramientas/ffmpeg/bin/ffmpeg.exe", True, INSTALAR),
    ("ffprobe", "herramientas/ffmpeg/bin/ffprobe.exe", True, INSTALAR),
    ("rhubarb", "herramientas/rhubarb/rhubarb.exe", True, INSTALAR),
    ("modelos de segmentación (rembg)", "modelos/prep/segmentacion.onnx", False, INSTALAR_PREP),
    ("modelo de inpainting (LaMa)", "modelos/prep/lama.pt", False, INSTALAR_PREP),
]
_PAQUETES = [("PIL", "pillow"), ("numpy", "numpy"), ("yaml", "PyYAML"),
             ("edge_tts", "edge-tts")]


def revisar_dependencias(raiz: Path) -> List[Dependencia]:
    raiz = Path(raiz)
    estados: List[Dependencia] = []

    ok_py = sys.version_info[:2] == (3, 11)
    estados.append(Dependencia(
        "python 3.11", ok_py, f"versión {sys.version.split()[0]}",
        "" if ok_py else "Usa el entorno del proyecto (.venv) creado con Python 3.11",
        None, True))

    for modulo, paquete in _PAQUETES:
        ok = importlib.util.find_spec(modulo) is not None
        estados.append(Dependencia(
            f"paquete {paquete}", ok, "instalado" if ok else "no instalado",
            "" if ok else f"{INSTALAR} (instala {paquete})", None, True))

    for nombre, ruta, requerida, accion in _ARCHIVOS:
        existe = (raiz / ruta).is_file()
        estados.append(Dependencia(
            nombre, existe, ruta if existe else f"falta {ruta}",
            "" if existe else accion, ruta, requerida))
    return estados


def todo_ok(estados: List[Dependencia]) -> bool:
    return all(e.ok for e in estados if e.requerida)


def formato_informe(estados: List[Dependencia]) -> str:
    lineas = []
    for e in estados:
        marca = "OK " if e.ok else ("FALTA" if e.requerida else "opcional")
        lineas.append(f"[{marca:<8}] {e.nombre}: {e.detalle}")
        if not e.ok:
            lineas.append(f"           Qué hacer: {e.accion}")
    lineas.append("")
    lineas.append("Entorno listo." if todo_ok(estados) else "Faltan dependencias obligatorias.")
    return "\n".join(lineas)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # acentos en la consola de Windows
    raiz = Path(__file__).resolve().parent.parent
    estados = revisar_dependencias(raiz)
    print(formato_informe(estados))
    return 0 if todo_ok(estados) else 1


if __name__ == "__main__":
    sys.exit(main())
