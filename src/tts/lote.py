"""Audios en lote (FR-014): un <id>.mp3 junto a cada <id>.txt, con reintentos y reanudable."""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from src.errores import AssetInvalido, TTSNoDisponible
from src.registro import obtener_logger
from src.tts.base import OpcionesTTS, ProveedorTTS
from src.tts.comun import limpiar_etiquetas, sintetizar_texto

log = obtener_logger("tts.lote")
EXTENSIONES_AUDIO = (".mp3", ".wav")


@dataclass
class ResumenLote:
    generados: int = 0
    omitidos: int = 0
    pendientes: List[str] = field(default_factory=list)
    vacios: List[str] = field(default_factory=list)
    error: Optional[TTSNoDisponible] = None


def generar_audios_en_lote(carpeta: Path, proveedor: ProveedorTTS, opciones: OpcionesTTS,
                           dormir: Callable[[float], None] = time.sleep,
                           ffmpeg: Optional[Path] = None) -> ResumenLote:
    """Se detiene si el proveedor no se recupera tras los reintentos (p. ej. cuota diaria):
    lo hecho se conserva y al volver a lanzarlo se reanuda donde quedó."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise AssetInvalido(f"No existe la carpeta de guiones {carpeta}",
                            "Crea la carpeta y deja en ella los guiones <id>.txt")
    resumen = ResumenLote()
    guiones = sorted(carpeta.glob("*.txt"))
    for i, guion in enumerate(guiones):
        id_clase = guion.stem
        if any(guion.with_suffix(ext).is_file() for ext in EXTENSIONES_AUDIO):
            resumen.omitidos += 1
            continue
        texto = guion.read_text(encoding="utf-8")
        if not limpiar_etiquetas(texto):
            resumen.vacios.append(id_clase)
            log.warning("%s: el guion no tiene texto; se omite", id_clase)
            continue
        destino = guion.with_suffix("." + proveedor.extension)
        t0 = time.perf_counter()
        try:
            sintetizar_texto(proveedor, texto, destino, opciones, ffmpeg=ffmpeg, dormir=dormir)
        except TTSNoDisponible as exc:
            resumen.error = exc
            resumen.pendientes = [g.stem for g in guiones[i:]
                                  if not any(g.with_suffix(e).is_file() for e in EXTENSIONES_AUDIO)
                                  and limpiar_etiquetas(g.read_text(encoding="utf-8"))]
            log.error("Se detuvo en %s: %s", id_clase, exc)
            return resumen
        resumen.generados += 1
        log.info("%s: audio generado en %.1f s (%d/%d)", id_clase, time.perf_counter() - t0, i + 1, len(guiones))
    return resumen
