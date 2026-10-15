"""Tratamiento del guion. Los guiones originales son texto plano; las etiquetas y las
marcas del TTS van entre corchetes y nunca deben llegar al análisis de visemas (FR-012)."""
import re

_MARCAS = re.compile(r"\[[^\]]*\]")
_ESPACIOS = re.compile(r"\s+")


def limpiar_para_analisis(texto: str) -> str:
    """Quita toda marca entre corchetes y normaliza espacios y saltos de línea."""
    return _ESPACIOS.sub(" ", _MARCAS.sub(" ", texto)).strip()
