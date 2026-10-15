"""Trabajadores del lote (FR-102, FR-103, FR-104, FR-106, FR-107).

`procesar_cola` es el bucle de un trabajador; `correr` lanza varios como procesos aparte y vigila
el progreso. Un fallo de un trabajo nunca detiene la cola; si el disco se llena, los trabajadores
esperan y retoman al liberarse espacio."""
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

from src import rutas
from src.audio import SIN_VENTANA
from src.errores import ErrorAccionable
from src.lote.cola import Cola, Trabajo
from src.lote.estado import resumen_texto
from src.registro import obtener_logger
from src.render import ParametrosRender, renderizar

GB = 1024 ** 3
LATIDO_S = 10
ESPERA_DISCO_S = 30
HUERFANO_S = 60
log = obtener_logger("lote")


def parametros_de(t: Trabajo, raiz: Path) -> ParametrosRender:
    """La semilla de cada clase se deriva de su id (FR-107); una semilla manual la desplaza."""
    audio = Path(t.audio) if t.audio else Path(raiz) / "clases" / f"{t.id}.mp3"
    ancho, alto = (int(v) for v in t.resolucion.split("x"))
    primero = lambda lista: (lista.split(";")[0].strip() or None) if lista else None
    return ParametrosRender(personaje=t.personaje, audio=audio, guion=Path(t.guion) if t.guion else None,
                            pose=primero(t.poses), escenario=primero(t.escenarios), resolucion=(ancho, alto),
                            semilla=t.semilla or 0, clase_id=t.id)


def ejecutar_trabajo(t: Trabajo, raiz: Path) -> Path:
    """Genera la voz si falta el audio (FR-010) y renderiza la clase."""
    params = parametros_de(t, raiz)
    if not params.audio.is_file():
        from src.cli import generar_voz
        params.audio = generar_voz(params.guion, t.tts, raiz, t.genero)
    return renderizar(params, raiz)


def salida_existente(raiz: Path, id_clase: str) -> Optional[Path]:
    for f in sorted((Path(raiz) / "salidas").glob(f"{id_clase}_*.mp4")):
        if not f.name.endswith(".part.mp4") and f.stat().st_size > 0:
            return f
    return None


def preparar_reanudacion(cola: Cola, raiz: Path, max_edad_s: float = HUERFANO_S) -> List[str]:
    """Antes de arrancar: los trabajos que quedaron 'en proceso' de una ejecución interrumpida
    vuelven a la cola y se borran los .part.mp4 que dejaron."""
    recuperados = cola.recuperar_huerfanos(max_edad_s)
    salidas = Path(raiz) / "salidas"
    ahora = time.time()
    for parcial in salidas.glob("*.part.mp4"):
        de_recuperado = any(parcial.name.startswith(f"{i}_") for i in recuperados)
        if de_recuperado or ahora - parcial.stat().st_mtime > max_edad_s:
            parcial.unlink(missing_ok=True)
    return recuperados


class _Latido(threading.Thread):
    def __init__(self, cola: Cola, id_trabajo: str, cada_s: float):
        super().__init__(daemon=True)
        self.cola, self.id_trabajo, self.cada_s, self.parar = cola, id_trabajo, cada_s, threading.Event()

    def run(self) -> None:
        while not self.parar.wait(self.cada_s):
            try:
                self.cola.latido(self.id_trabajo)
            except Exception:
                pass


def procesar_cola(cola: Cola, raiz: Path, ejecutor: Callable[[Trabajo, Path], Path] = ejecutar_trabajo,
                  espacio_libre: Callable[[Path], int] = lambda p: shutil.disk_usage(p).free,
                  espacio_minimo_gb: float = 20, dormir: Callable[[float], None] = time.sleep,
                  lote: Optional[str] = None, latido_s: float = LATIDO_S) -> None:
    """Bucle de un trabajador: reclama, ejecuta y registra hasta que no quedan pendientes."""
    salidas = Path(raiz) / "salidas"
    salidas.mkdir(parents=True, exist_ok=True)
    while True:
        libre = espacio_libre(salidas)
        if libre < espacio_minimo_gb * GB:
            log.warning("Espacio libre insuficiente (%.1f GB < %g GB): en pausa hasta que se libere espacio",
                        libre / GB, espacio_minimo_gb)
            dormir(ESPERA_DISCO_S)
            continue
        t = cola.reclamar(lote)
        if t is None:
            return
        previo = salida_existente(raiz, t.id)
        if previo is not None:
            cola.terminar(t.id, str(previo))
            continue
        latido = _Latido(cola, t.id, latido_s)
        latido.start()
        try:
            cola.terminar(t.id, str(ejecutor(t, raiz)))
        except ErrorAccionable as exc:
            cola.fallar(t.id, str(exc))
            log.error("%s: %s", t.id, exc)
        except Exception as exc:                       # un error raro de una clase no tumba el lote
            cola.fallar(t.id, f"Error inesperado ({type(exc).__name__}: {exc}). Qué hacer: revisa logs/{t.id}.log")
            log.exception("%s: error inesperado", t.id)
        finally:
            latido.parar.set()


def correr(raiz: Path, db: Path, trabajadores: int, espacio_minimo_gb: float, lote: Optional[str] = None,
           intervalo_s: float = 15) -> int:
    """Lanza `trabajadores` procesos y muestra el progreso. Devuelve 0 si todo salió bien y 1 si
    alguna clase quedó con error."""
    cola = Cola(db)
    recuperados = preparar_reanudacion(cola, raiz)
    if recuperados:
        log.info("Se retoman %d trabajos que habían quedado a medias", len(recuperados))
    procesos = []
    for _ in range(max(1, trabajadores)):
        cmd = [sys.executable, "-m", "src.lote", "trabajador", "--raiz", str(raiz), "--db", str(db),
               "--espacio-minimo-gb", str(espacio_minimo_gb)]
        if lote:
            cmd += ["--lote", lote]
        procesos.append(subprocess.Popen(cmd, cwd=rutas.RAIZ, creationflags=SIN_VENTANA))
    try:
        while any(p.poll() is None for p in procesos):
            time.sleep(intervalo_s)
            print(resumen_texto(cola, lote).splitlines()[0], file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        log.warning("Interrumpido: los trabajos a medias se retomarán al volver a ejecutar")
        for p in procesos:
            p.terminate()
        return 2
    print("\n" + resumen_texto(cola, lote), flush=True)
    return 1 if cola.resumen(lote)["error"] else 0
