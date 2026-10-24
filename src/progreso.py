"""Seguimiento en vivo de una clase: cada etapa del trabajo (voz, assets, Rhubarb, línea de tiempo, capas, render) con su inicio y
su fin en milisegundos, y el avance de cuadros del render. Se escribe en `logs/progreso/<clase>.json` (atómico, sin bloquear el
render si falla) y la interfaz lo lee para mostrar los cronómetros en vivo.

Una clase = un seguimiento. `con_seguimiento` lo abre y lo cierra; las etapas se anotan solas porque `registro.etapa` avisa aquí."""
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, List, Optional

from src import registro

INTERVALO_AVANCE_S = 0.2            # como mucho cinco escrituras por segundo del avance de cuadros
CADUCIDAD_S = 120                   # sin actualizarse en tanto tiempo, un trabajo «en curso» pasa a «sin señal» (proceso caído)
MAX_EDAD_S = 24 * 3600

_actual: Optional["SeguimientoClase"] = None


class SeguimientoClase:
    def __init__(self, raiz: Path, clase: str, reloj: Callable[[], float] = time.time):
        self.reloj = reloj
        self.clase = clase
        self.ruta = Path(raiz) / "logs" / "progreso" / f"{clase}.json"
        self.inicio_ms = self._ms()
        self.fin_ms: Optional[int] = None
        self.estado = "en_curso"
        self.etapas: List[dict] = []
        self.actual: Optional[str] = None
        self.n = self.total = 0
        self.fraccion = 0.0
        self.error = ""
        self.escrituras = 0
        self._ultimo = float("-inf")
        self._cerrojo = threading.Lock()
        self._escribir()

    def _ms(self) -> int:
        return int(round(self.reloj() * 1000))

    def _datos(self) -> dict:
        return {"clase": self.clase, "estado": self.estado, "inicio_ms": self.inicio_ms, "fin_ms": self.fin_ms,
                "actualizado_ms": self._ms(), "actual": self.actual, "etapas": self.etapas, "n": self.n, "total": self.total,
                "fraccion": self.fraccion, "error": self.error}

    def _escribir(self) -> None:
        """Mejor esfuerzo: un fallo de disco o un lector que tiene el archivo abierto nunca debe romper el render."""
        with self._cerrojo:
            try:
                self.ruta.parent.mkdir(parents=True, exist_ok=True)
                temporal = self.ruta.with_suffix(".tmp")
                temporal.write_text(json.dumps(self._datos(), ensure_ascii=False), encoding="utf-8")
                os.replace(temporal, self.ruta)
                self.escrituras += 1
                self._ultimo = self.reloj()
            except OSError:
                pass

    def _abierta(self, nombre: str) -> Optional[dict]:
        return next((e for e in reversed(self.etapas) if e["nombre"] == nombre and e["fin_ms"] is None), None)

    def empezar(self, nombre: str) -> None:
        self.etapas.append({"nombre": nombre, "inicio_ms": self._ms(), "fin_ms": None, "estado": "en_curso"})
        self.actual = nombre
        self._escribir()

    def terminar(self, nombre: str, ok: bool = True) -> None:
        e = self._abierta(nombre)
        if e is not None:
            e["fin_ms"], e["estado"] = self._ms(), "ok" if ok else "error"
        abiertas = [x["nombre"] for x in self.etapas if x["fin_ms"] is None]
        self.actual = abiertas[-1] if abiertas else None
        self._escribir()

    def avance(self, n: int, total: int) -> None:
        self.n, self.total = int(n), int(total)
        self.fraccion = round(self.n / self.total, 4) if self.total else 0.0
        if n >= total or self.reloj() - self._ultimo >= INTERVALO_AVANCE_S:
            self._escribir()

    def cerrar(self, estado: str, error: str = "") -> None:
        ahora = self._ms()
        for e in self.etapas:
            if e["fin_ms"] is None:
                e["fin_ms"], e["estado"] = ahora, "error" if estado == "error" else "ok"
        self.estado, self.fin_ms, self.actual, self.error = estado, ahora, None, error[:300]
        self._escribir()

    def _evento(self, evento: str, nombre: str) -> None:           # lo llama registro.etapa
        if evento == "inicio":
            self.empezar(nombre)
        else:
            self.terminar(nombre, ok=evento == "fin")


@contextmanager
def con_seguimiento(raiz: Path, clase: str, reloj: Callable[[], float] = time.time) -> Iterator[SeguimientoClase]:
    """Abre el seguimiento de una clase (o reutiliza el que ya esté abierto) y lo cierra al salir: «hecha» o «error»."""
    global _actual
    if _actual is not None:
        yield _actual
        return
    s = SeguimientoClase(raiz, clase, reloj)
    _actual = s
    registro.escuchar(s._evento)
    try:
        yield s
    except BaseException as exc:
        s.cerrar("error", f"{type(exc).__name__}: {exc}")
        raise
    else:
        s.cerrar("hecha")
    finally:
        registro.dejar_de_escuchar(s._evento)
        _actual = None


def avance(n: int, total: int) -> None:
    """Avance de cuadros del render; no hace nada si no hay un seguimiento abierto."""
    if _actual is not None:
        _actual.avance(n, total)


def leer_todos(raiz: Path, ahora_ms: Optional[int] = None, caducidad_s: float = CADUCIDAD_S, limite: int = 40) -> List[dict]:
    """Los seguimientos recientes, el más nuevo primero. Un «en curso» que no se actualiza hace rato figura como «sin_senal»."""
    ahora_ms = int(time.time() * 1000) if ahora_ms is None else ahora_ms
    carpeta = Path(raiz) / "logs" / "progreso"
    salida = []
    for f in carpeta.glob("*.json") if carpeta.is_dir() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            edad_s = (ahora_ms - int(d["actualizado_ms"])) / 1000
        except (ValueError, KeyError, OSError, TypeError):
            continue
        if edad_s > MAX_EDAD_S:
            continue
        if d.get("estado") == "en_curso" and edad_s > caducidad_s:
            d["estado"] = "sin_senal"
        salida.append(d)
    return sorted(salida, key=lambda d: d.get("inicio_ms", 0), reverse=True)[:limite]
