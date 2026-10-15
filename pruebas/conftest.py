"""Fixtures compartidas. Todas las pruebas de archivos corren en una ruta con espacios
y acentos para cumplir NFR-005 (caso real: C:\\Users\\Juan 02\\...)."""
from pathlib import Path

import pytest

CARPETAS_PROYECTO = (
    "src", "herramientas", "modelos", "entrada", "clases", "salidas", "cache", "logs",
    "lote/manifiestos", "personajes", "escenarios",
)


@pytest.fixture
def proyecto_tmp(tmp_path: Path) -> Path:
    """Proyecto temporal con la estructura de carpetas, en una ruta difícil."""
    raiz = tmp_path / "Proyecto de Prueba áéíóú ñandú"
    for carpeta in CARPETAS_PROYECTO:
        (raiz / carpeta).mkdir(parents=True)
    return raiz


@pytest.fixture
def proyecto_con_assets(proyecto_tmp: Path) -> Path:
    """Proyecto temporal con una pose placeholder (P1) y un escenario (E1), listo para renderizar."""
    from PIL import Image
    from src.biblioteca.placeholders import crear_pose_placeholder
    crear_pose_placeholder(proyecto_tmp / "personajes" / "profe" / "poses" / "P1_demo", "P1", lienzo=(1280, 720))
    fondo = proyecto_tmp / "escenarios" / "E1_aula" / "fondo.png"
    fondo.parent.mkdir(parents=True)
    Image.new("RGB", (1280, 720), (90, 140, 200)).save(fondo)
    return proyecto_tmp
