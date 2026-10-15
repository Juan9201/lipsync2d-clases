"""Registro (logs) por etapa con tiempos, y archivo opcional por trabajo (P9)."""
import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

FORMATO = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _ConsolaActual(logging.StreamHandler):
    """Escribe siempre en el sys.stderr vigente (no en uno capturado al crear el logger)."""

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, valor):
        pass


def obtener_logger(nombre: str, archivo: Optional[Path] = None) -> logging.Logger:
    """Logger con salida a consola y, si se indica, a un archivo UTF-8 (uno por trabajo)."""
    log = logging.getLogger(nombre)
    log.setLevel(logging.INFO)
    if not any(getattr(h, "_lipsync_consola", False) for h in log.handlers):
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(errors="replace")   # nunca fallar por un carácter no codificable
        consola = _ConsolaActual()
        consola.setFormatter(logging.Formatter(FORMATO))
        consola._lipsync_consola = True  # marca para no duplicar handlers
        log.addHandler(consola)
    if archivo is not None:
        archivo = Path(archivo)
        archivo.parent.mkdir(parents=True, exist_ok=True)
        # Un solo archivo por logger: al pasar a otra clase se cierra el anterior (un trabajador
        # procesa miles de clases y no debe acumular manejadores ni mezclar sus mensajes).
        for h in [h for h in log.handlers if hasattr(h, "baseFilename") and h.baseFilename != str(archivo.resolve())]:
            log.removeHandler(h)
            h.close()
        if not any(getattr(h, "baseFilename", None) == str(archivo.resolve()) for h in log.handlers):
            fh = logging.FileHandler(archivo, encoding="utf-8")
            fh.setFormatter(logging.Formatter(FORMATO))
            log.addHandler(fh)
    return log


@contextmanager
def etapa(log: logging.Logger, nombre: str) -> Iterator[dict]:
    """Registra inicio, fin y duración de una etapa; ante un error lo registra y lo relanza.
    El diccionario devuelto recibe `duracion_s` al terminar."""
    info: dict = {}
    log.info("[%s] inicio", nombre)
    t0 = time.perf_counter()
    try:
        yield info
    except Exception as exc:
        info["duracion_s"] = time.perf_counter() - t0
        log.error("[%s] error tras %.2f s: %s", nombre, info["duracion_s"], exc)
        raise
    info["duracion_s"] = time.perf_counter() - t0
    log.info("[%s] fin en %.2f s", nombre, info["duracion_s"])
