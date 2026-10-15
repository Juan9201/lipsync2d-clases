"""Candado entre procesos basado en un directorio (os.mkdir es atómico en Windows).
La webapp de voz numera sus archivos listando su carpeta: con varios trabajadores (procesos
distintos) hay que dejar pasar las peticiones de una en una."""
import os
import time
from pathlib import Path

from src.errores import TTSNoDisponible


class CandadoArchivo:
    def __init__(self, ruta: Path, timeout_s: float = 900.0, obsoleto_s: float = 900.0, espera_s: float = 0.2):
        self.ruta = Path(ruta)
        self.timeout_s, self.obsoleto_s, self.espera_s = timeout_s, obsoleto_s, espera_s

    def __enter__(self) -> "CandadoArchivo":
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        limite = time.monotonic() + self.timeout_s
        while True:
            try:
                os.mkdir(self.ruta)
                return self
            except FileExistsError:
                try:                                   # candado de un proceso que murió: se rompe
                    if time.time() - self.ruta.stat().st_mtime > self.obsoleto_s:
                        os.rmdir(self.ruta)
                        continue
                except OSError:
                    pass
                if time.monotonic() > limite:
                    raise TTSNoDisponible(
                        f"Otro proceso mantuvo ocupada la voz durante más de {self.timeout_s:.0f} s",
                        f"Cierra los procesos de render que estén colgados o borra la carpeta {self.ruta}")
                time.sleep(self.espera_s)

    def __exit__(self, *exc) -> None:
        try:
            os.rmdir(self.ruta)
        except OSError:
            pass
