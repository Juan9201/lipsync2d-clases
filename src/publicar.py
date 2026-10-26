"""Subtitular y publicar: lo que sale del render (y las clases humanas que dejes en la carpeta de entrada) pasa por la herramienta de subtítulos
y termina en Drive, ordenado por nivel y módulo.

    render (salidas/<clase>_<fecha>.mp4) ─┐
    clases humanas (carpeta de entrada)  ─┴→  subtítulos (una a la vez: una sola GPU)  →  salidas/subtitulados/  →  Drive\\<Nivel>\\<Mxx>\\

Estado en `lote/publicacion.db` (una fila por clase): pendiente → subtitulado → publicado, o error. Si Drive no está disponible la clase queda
«subtitulado» y la copia se reintenta en la siguiente vuelta; si falla la herramienta de subtítulos se reintenta con `reintentar`.
La carpeta de Drive y la de entrada se configuran en `publicacion.yaml`.

Uso:  python -m src.publicar correr [--una-vez]      procesa lo pendiente (sin --una-vez espera a que acabe el lote de render)
      python -m src.publicar encolar A1-M05-3 ...    manda a subtitular clases ya renderizadas
      python -m src.publicar estado | reintentar
"""
import argparse
import re
import shutil
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

import yaml

from src import rutas
from src.errores import ErrorAccionable

CONFIG_DEFECTO = {
    "drive": "G:/My Drive/Clases renderizadas",
    "entrada_humano": "G:/My Drive/Clases humano/entrada",
    "conservar_local": True,
}
_ID = re.compile(r"^([AB][12])-M(\d{2})-(\d)(?![\d])")
_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ESPERA_TAMANO_S = 60.0
MAX_INTENTOS = 4                  # tras tantos fallos seguidos la clase pasa a «error» y deja de bloquear a las demás

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS pub (
    id TEXT PRIMARY KEY, origen TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'pendiente', video TEXT, srt TEXT,
    destino TEXT, error TEXT DEFAULT '', intentos INTEGER DEFAULT 0, inicio REAL DEFAULT 0, fin REAL DEFAULT 0, orden INTEGER
);
"""


def cargar_config(raiz: Path) -> dict:
    cfg = dict(CONFIG_DEFECTO)
    ruta = Path(raiz) / "publicacion.yaml"
    if ruta.is_file():
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        if not isinstance(datos, dict):
            raise ErrorAccionable(f"{ruta.name} debe ser un diccionario YAML", "Usa claves drive, entrada_humano, conservar_local")
        cfg.update(datos)
    return cfg


def partes_de_id(id_clase: str):
    m = _ID.match(id_clase)
    if not m:
        raise ErrorAccionable(f"«{id_clase}» no es un id de clase (como A1-M05-3)", "Nombra el video con el id de la clase al principio")
    return m.group(1), f"M{m.group(2)}"


def carpeta_drive(cfg: dict, id_clase: str) -> Path:
    nivel, modulo = partes_de_id(id_clase)
    return Path(cfg["drive"]) / nivel / modulo


class Registro:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as c:
            c.executescript(_ESQUEMA)

    @contextmanager
    def _con(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.ruta, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def agregar(self, id_clase: str, origen: str, video: Path) -> bool:
        with self._con() as c:
            if c.execute("SELECT 1 FROM pub WHERE id=?", (id_clase,)).fetchone():
                return False
            n = (c.execute("SELECT COALESCE(MAX(orden),0) FROM pub").fetchone()[0]) + 1
            c.execute("INSERT INTO pub(id, origen, video, orden) VALUES (?,?,?,?)", (id_clase, origen, str(video), n))
            return True

    def siguiente(self, estados=("pendiente", "subtitulado")) -> Optional[sqlite3.Row]:
        with self._con() as c:
            marcas = ",".join("?" * len(estados))
            # primero lo que no ha fallado: una clase atascada nunca bloquea a las demás
            return c.execute(f"SELECT * FROM pub WHERE estado IN ({marcas}) ORDER BY (error != ''), (estado='subtitulado') DESC, orden LIMIT 1",
                             estados).fetchone()

    def poner(self, id_clase: str, **campos) -> None:
        with self._con() as c:
            c.execute(f"UPDATE pub SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?", (*campos.values(), id_clase))

    def todas(self) -> List[dict]:
        with self._con() as c:
            return [dict(r) for r in c.execute("SELECT * FROM pub ORDER BY orden")]

    def reintentar(self) -> int:
        with self._con() as c:
            return c.execute("UPDATE pub SET estado = CASE WHEN srt IS NOT NULL AND srt != '' THEN 'subtitulado' ELSE 'pendiente' END, "
                             "error='' WHERE estado='error'").rowcount


def _video_de_render(raiz: Path, id_clase: str) -> Optional[Path]:
    for f in sorted((Path(raiz) / "salidas").glob(f"{id_clase}_*.mp4"), reverse=True):
        if not f.name.endswith(".part.mp4") and "_subtitulado" not in f.name and f.stat().st_size > 0:
            return f
    return None


def descubrir(raiz: Path, registro: Registro, cfg: dict) -> int:
    """Anota lo nuevo: clases de IA con el render terminado (cola) y videos de clases humanas en la carpeta de entrada."""
    nuevas = 0
    cola = Path(raiz) / "lote" / "cola.db"
    if cola.is_file():
        c = sqlite3.connect(cola, timeout=30)
        try:
            for (id_clase, salida) in c.execute("SELECT id, salida FROM trabajos WHERE estado='hecho' AND salida != '' ORDER BY orden"):
                v = Path(salida)
                if _ID.match(id_clase) and v.is_file() and "prueba_" not in v.name and registro.agregar(id_clase, "ia", v):
                    nuevas += 1
        finally:
            c.close()
    entrada = Path(cfg["entrada_humano"])
    if entrada.is_dir():
        for f in sorted(entrada.iterdir()):
            if f.is_file() and f.suffix.lower() in _VIDEO and _ID.match(f.name):
                id_clase = _ID.match(f.name).group(0)
                if registro.agregar(id_clase, "humano", f):
                    nuevas += 1
    return nuevas


def _copiar_a_drive(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name("." + destino.name + ".part")
    shutil.copyfile(origen, parcial)
    # Drive para escritorio informa un tamaño parcial (múltiplo de 1 MiB) un instante después de copiar: se espera a que se asiente
    limite = time.monotonic() + ESPERA_TAMANO_S
    while parcial.stat().st_size != origen.stat().st_size and time.monotonic() < limite:
        time.sleep(1.0)
    if parcial.stat().st_size != origen.stat().st_size:
        parcial.unlink(missing_ok=True)
        raise ErrorAccionable(f"La copia de {origen.name} a Drive quedó incompleta", "Reintenta; revisa el espacio y la conexión de Drive")
    parcial.replace(destino)


def procesar_una(raiz: Path, registro: Registro, cfg: dict, subtitular: Optional[Callable] = None,
                 al_avanzar: Optional[Callable[[str, str], None]] = None) -> Optional[str]:
    """Subtitula (si falta) y publica la siguiente clase pendiente. Devuelve su id, o None si no hay nada."""
    from src.progreso import SeguimientoClase
    if subtitular is None:
        from src.subtitulos import subtitular as subtitular_api
        subtitular = subtitular_api
    fila = registro.siguiente()
    if fila is None:
        return None
    id_clase, aviso = fila["id"], al_avanzar or (lambda _i, _t: None)
    seg = SeguimientoClase(raiz, f"{id_clase}_subtitulos")           # la interfaz lo muestra como una tarjeta más en «En vivo»
    registro.poner(id_clase, inicio=time.time(), intentos=fila["intentos"] + 1, error="")
    estado = fila["estado"]
    video, srt = fila["video"], fila["srt"]
    try:
        if estado == "pendiente":
            seg.empezar("subtitulando")
            try:
                r = subtitular(Path(video), Path(raiz) / "salidas" / "subtitulados", id_clase, raiz,
                               lambda t: (aviso(id_clase, t), seg._escribir()))
            except BaseException:
                seg.terminar("subtitulando", ok=False)
                raise
            seg.terminar("subtitulando")
            estado, video, srt = "subtitulado", str(r["video"]), str(r["srt"])
            registro.poner(id_clase, estado=estado, video=video, srt=srt)
        if not Path(cfg["drive"]).parent.exists():                     # Drive no montado: se reintenta en la siguiente vuelta
            registro.poner(id_clase, error="Drive no disponible (se reintenta)")
            seg.cerrar("hecha")
            return id_clase
        seg.empezar("publicando")
        destino = carpeta_drive(cfg, id_clase)
        for ruta in (Path(video), Path(srt)):
            _copiar_a_drive(ruta, destino / ruta.name)
        seg.terminar("publicando")
        registro.poner(id_clase, estado="publicado", destino=str(destino), fin=time.time())
        if fila["origen"] == "humano":                                 # el original ya no hace falta en la entrada
            origen = next((f for f in Path(cfg["entrada_humano"]).glob(f"{id_clase}*") if f.suffix.lower() in _VIDEO), None)
            if origen is not None:
                procesadas = Path(cfg["entrada_humano"]).parent / "procesadas"
                procesadas.mkdir(parents=True, exist_ok=True)
                shutil.move(str(origen), str(procesadas / origen.name))
        if not cfg.get("conservar_local", True):
            for ruta in (Path(video), Path(srt)):
                ruta.unlink(missing_ok=True)
        seg.cerrar("hecha")
    except Exception as exc:                                           # un fallo de una clase no detiene a las demás
        mensaje = str(exc) if isinstance(exc, ErrorAccionable) else f"{type(exc).__name__}: {exc}"
        agotada = fila["intentos"] + 1 >= MAX_INTENTOS
        registro.poner(id_clase, estado="error" if estado == "pendiente" or agotada else "subtitulado", error=mensaje[:400])
        seg.cerrar("error", mensaje)
    return id_clase


def _lote_activo(raiz: Path) -> bool:
    cola = Path(raiz) / "lote" / "cola.db"
    if not cola.is_file():
        return False
    c = sqlite3.connect(cola, timeout=30)
    try:
        return bool(c.execute("SELECT 1 FROM trabajos WHERE estado IN ('pendiente','en_proceso') LIMIT 1").fetchone())
    finally:
        c.close()


def correr(raiz: Path, una_vez: bool = False, espera_s: float = 15.0, subtitular: Optional[Callable] = None) -> Dict[str, int]:
    """Procesa lo pendiente de a una clase. Sin `una_vez`, sigue esperando clases nuevas mientras el lote de render siga trabajando."""
    raiz = Path(raiz)
    cfg = cargar_config(raiz)
    registro = Registro(raiz / "lote" / "publicacion.db")
    hechas, fallidas = 0, 0
    while True:
        descubrir(raiz, registro, cfg)
        id_clase = procesar_una(raiz, registro, cfg, subtitular, lambda i, t: print(f"[{i}] {t}", flush=True))
        if id_clase is not None:
            fila = next(f for f in registro.todas() if f["id"] == id_clase)
            print(f"{id_clase}: {fila['estado']}" + (f" ({fila['error']})" if fila["error"] else ""), flush=True)
            hechas += fila["estado"] == "publicado"
            fallidas += fila["estado"] == "error"
            if fila["estado"] == "subtitulado":                 # Drive no disponible: no insistir sin pausa
                time.sleep(espera_s)
            continue
        if una_vez or not _lote_activo(raiz):
            break
        time.sleep(espera_s)
    return {"publicadas": hechas, "con_error": fallidas}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    c = sub.add_parser("correr")
    c.add_argument("--una-vez", action="store_true")
    e = sub.add_parser("encolar")
    e.add_argument("clases", nargs="+")
    sub.add_parser("estado")
    sub.add_parser("reintentar")
    a = ap.parse_args(argv)
    raiz = rutas.RAIZ
    reg = Registro(raiz / "lote" / "publicacion.db")
    if a.orden == "correr":
        print(correr(raiz, una_vez=a.una_vez))
    elif a.orden == "encolar":
        for id_clase in a.clases:
            partes_de_id(id_clase)
            v = _video_de_render(raiz, id_clase)
            print(f"{id_clase}: " + ("encolada" if v and reg.agregar(id_clase, "ia", v) else "sin video renderizado o ya estaba"))
    elif a.orden == "estado":
        for f in reg.todas():
            print(f"{f['id']:<10} {f['estado']:<12} {f['error'][:80]}")
    else:
        print(f"{reg.reintentar()} clase(s) vuelven a la cola")
    return 0


if __name__ == "__main__":
    sys.exit(main())
