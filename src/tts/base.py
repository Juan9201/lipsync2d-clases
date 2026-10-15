"""Interfaz de proveedor TTS (contrato proveedor-tts.md)."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from src.errores import TTSNoDisponible


@dataclass(frozen=True)
class OpcionesTTS:
    """Cada proveedor usa las opciones que le aplican e ignora el resto. Lo que sea None
    no se envía, y el proveedor usa su valor por defecto."""
    voz: Optional[str] = None
    idioma: Optional[str] = None
    estilo: str = ""
    velocidad: str = "normal"
    tono: str = "normal"
    temperatura: float = 1.0
    modelo: Optional[str] = None


@dataclass(frozen=True)
class EstadoProveedor:
    ok: bool
    detalle: str


class TTSReintentable(TTSNoDisponible):
    """Fallo transitorio (cuota por minuto, 5xx, red): vale la pena reintentar."""


class ProveedorTTS(Protocol):
    nombre: str
    extension: str            # "mp3" o "wav"
    limite_caracteres: int    # tamaño máximo de texto por petición
    max_reintentos: int       # intentos totales ante fallos transitorios

    def comprobar(self) -> EstadoProveedor: ...

    def sintetizar(self, texto: str, destino: Path, opciones: OpcionesTTS) -> Path:
        """Escribe el audio en `destino`; lanza TTSNoDisponible ante cualquier fallo (FR-013)."""
