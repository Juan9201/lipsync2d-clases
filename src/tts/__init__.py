"""Módulo de voz: proveedores intercambiables `gemini-studio` (defecto) y `edge`.
La configuración (género, voz, idioma, estilo…) se lee de tts.yaml en la raíz del proyecto.

El género (hombre | mujer) elige la voz de cada proveedor, para cambiar de profesor o
profesora tocando una sola línea. Una `voz` explícita en tts.yaml manda sobre el género."""
from pathlib import Path
from typing import Optional, Tuple

import yaml

from src import rutas
from src.errores import TTSNoDisponible
from src.tts.base import OpcionesTTS, ProveedorTTS

PROVEEDORES = ("gemini-studio", "edge")
GENEROS = ("hombre", "mujer")
GENERO_DEFECTO = "hombre"

# Valores por defecto cuando tts.yaml no dice nada.
VOCES_DEFECTO = {
    "gemini-studio": {"hombre": "es-419-podcaster-3", "mujer": "es-419-podcaster-2"},
    "edge": {"hombre": "en-US-AndrewMultilingualNeural", "mujer": "en-US-AvaMultilingualNeural"},
}

def _config(raiz: Path) -> dict:
    ruta = Path(raiz) / "tts.yaml"
    if not ruta.is_file():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def obtener_proveedor(nombre: str, raiz: Path = rutas.RAIZ,
                      genero: Optional[str] = None) -> Tuple[ProveedorTTS, OpcionesTTS]:
    """Devuelve el proveedor y sus opciones según tts.yaml y el género pedido."""
    config = _config(raiz)
    genero = genero or config.get("genero") or GENERO_DEFECTO
    if genero not in GENEROS:
        raise TTSNoDisponible(f"Género de voz desconocido «{genero}»",
                              f"Usa «hombre» o «mujer» (en tts.yaml o con --genero)")
    cfg = config.get(nombre, {}) or {}
    voz = cfg.get("voz") or (cfg.get("voces") or {}).get(genero) or VOCES_DEFECTO.get(nombre, {}).get(genero)
    if nombre == "gemini-studio":
        from src.tts.gemini_studio import URL_DEFECTO, ProveedorGeminiStudio
        proveedor = ProveedorGeminiStudio(cfg.get("url", URL_DEFECTO))
    elif nombre == "edge":
        from src.tts.edge import ProveedorEdge
        proveedor = ProveedorEdge(voz)
    else:
        raise TTSNoDisponible(f"Proveedor de voz desconocido «{nombre}»",
                              f"Usa uno de: {', '.join(PROVEEDORES)}")
    opciones = OpcionesTTS(
        voz=voz, idioma=cfg.get("idioma"), estilo=cfg.get("estilo", "") or "",
        velocidad=cfg.get("velocidad", "normal"), tono=cfg.get("tono", "normal"),
        temperatura=float(cfg.get("temperatura", 1.0)), modelo=cfg.get("modelo_gemini"))
    return proveedor, opciones
