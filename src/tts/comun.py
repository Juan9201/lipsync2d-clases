"""Pre y postprocesado común a todos los proveedores: limpieza de etiquetas (FR-012),
partición, reintentos con espera exponencial y unión de audios."""
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from src import rutas
from src.audio import SIN_VENTANA, requerir
from src.errores import TTSNoDisponible
from src.tts.base import OpcionesTTS, ProveedorTTS, TTSReintentable

# Solo los prefijos reservados del proyecto; otras marcas ([short pause], [giggle]) son del TTS.
_ETIQUETA_PROPIA = re.compile(r"\[\s*(?:toma|pose|escenario|plano)\s*:[^\]]*\]", re.IGNORECASE)
_FIN_FRASE = re.compile(r"(?<=[.!?…])\s+")


def limpiar_etiquetas(texto: str) -> str:
    """Quita nuestras etiquetas de toma sin tocar las marcas del TTS ni los saltos de línea."""
    texto = _ETIQUETA_PROPIA.sub(" ", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" ?\n ?", "\n", texto)
    texto = re.sub(r" ([.,;:!?»)])", r"\1", texto)
    return texto.strip()


def _partir_largo(frase: str, limite: int) -> List[str]:
    trozos, actual = [], ""
    for palabra in frase.split():
        while len(palabra) > limite:                 # palabra imposible: corte duro
            if actual:
                trozos.append(actual); actual = ""
            trozos.append(palabra[:limite]); palabra = palabra[limite:]
        if not actual:
            actual = palabra
        elif len(actual) + 1 + len(palabra) <= limite:
            actual += " " + palabra
        else:
            trozos.append(actual); actual = palabra
    if actual:
        trozos.append(actual)
    return trozos


def partir_texto(texto: str, limite: int) -> List[str]:
    """Parte el texto por frases en trozos de como máximo `limite` caracteres."""
    texto = texto.strip()
    if not texto:
        return []
    if len(texto) <= limite:
        return [texto]
    frases: List[str] = []
    for parrafo in re.split(r"\n\s*\n", texto):
        parrafo = re.sub(r"\s+", " ", parrafo).strip()
        if parrafo:
            frases += _FIN_FRASE.split(parrafo)
    trozos, actual = [], ""
    for frase in frases:
        for pieza in ([frase] if len(frase) <= limite else _partir_largo(frase, limite)):
            if not actual:
                actual = pieza
            elif len(actual) + 1 + len(pieza) <= limite:
                actual += " " + pieza
            else:
                trozos.append(actual); actual = pieza
    if actual:
        trozos.append(actual)
    return trozos


def con_reintentos(fn: Callable, max_intentos: int = 5, espera_base: float = 2.0,
                   dormir: Callable[[float], None] = time.sleep,
                   aleatorio: Callable[[], float] = lambda: random.uniform(0, 1)):
    """Reintenta ante TTSReintentable con espera exponencial (2, 4, 8, 16…) más una variación
    aleatoria. Un error no reintentable sale de inmediato. Al agotar los intentos lanza un
    TTSNoDisponible con la causa y las alternativas."""
    ultimo: Optional[TTSReintentable] = None
    for intento in range(max_intentos):
        try:
            return fn()
        except TTSReintentable as exc:
            ultimo = exc
            if intento < max_intentos - 1:
                dormir(espera_base * (2 ** intento) + aleatorio())
    raise TTSNoDisponible(f"{ultimo.causa} (tras {max_intentos} intentos)", ultimo.sugerencia)


def unir_audios(partes: Sequence[Path], destino: Path, ffmpeg: Optional[Path] = None) -> Path:
    """Concatena audios del mismo formato sin recodificar."""
    ffmpeg = requerir(ffmpeg or rutas.FFMPEG)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    lista = destino.with_name(destino.name + ".lista.txt")
    lista.write_text("".join("file '{}'\n".format(Path(p).resolve().as_posix().replace("'", "'\\''"))
                             for p in partes), encoding="utf-8")
    try:
        r = subprocess.run([str(ffmpeg), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                            "-c", "copy", str(destino)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=SIN_VENTANA)
    finally:
        lista.unlink(missing_ok=True)
    if r.returncode != 0:
        raise TTSNoDisponible(f"No se pudieron unir los fragmentos de audio ({r.stderr.strip()[:200]})",
                              "Vuelve a intentarlo o usa un proveedor distinto con --tts")
    return destino


def sintetizar_texto(proveedor: ProveedorTTS, texto: str, destino: Path, opciones: OpcionesTTS,
                     ffmpeg: Optional[Path] = None, dormir: Callable[[float], None] = time.sleep) -> Path:
    """Texto -> audio completo: limpia etiquetas, parte, sintetiza cada trozo con reintentos,
    une y escribe el resultado de forma atómica (.part -> nombre final)."""
    destino = Path(destino)
    limpio = limpiar_etiquetas(texto)
    trozos = partir_texto(limpio, proveedor.limite_caracteres)
    if not trozos:
        raise TTSNoDisponible("El guion no tiene texto que convertir en voz",
                              "Escribe texto en el guion o entrega un audio propio con --audio")
    parcial = destino.with_name(destino.name + ".part")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporales: List[Path] = []
    try:
        if len(trozos) == 1:
            con_reintentos(lambda: proveedor.sintetizar(trozos[0], parcial, opciones),
                           proveedor.max_reintentos, dormir=dormir)
        else:
            for i, trozo in enumerate(trozos):
                t = destino.with_name(f"{destino.stem}.parte{i:03d}.{proveedor.extension}")
                temporales.append(t)
                con_reintentos(lambda t=t, trozo=trozo: proveedor.sintetizar(trozo, t, opciones),
                               proveedor.max_reintentos, dormir=dormir)
            unir_audios(temporales, parcial, ffmpeg)
        os.replace(parcial, destino)
    finally:
        for t in temporales:
            t.unlink(missing_ok=True)
        parcial.unlink(missing_ok=True)
    return destino
