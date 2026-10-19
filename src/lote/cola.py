"""Cola persistente de trabajos (FR-100, FR-102, FR-104): un archivo SQLite en modo WAL.
Cada proceso abre su propia conexión; el reclamo es atómico (BEGIN IMMEDIATE), así que dos
trabajadores nunca toman el mismo trabajo."""
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

ESQUEMA = """
CREATE TABLE IF NOT EXISTS trabajos (
    orden INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL, lote TEXT NOT NULL DEFAULT '', personaje TEXT NOT NULL DEFAULT 'profesor',
    audio TEXT, guion TEXT, poses TEXT NOT NULL DEFAULT '', escenarios TEXT NOT NULL DEFAULT '',
    resolucion TEXT NOT NULL DEFAULT '1280x720', semilla INTEGER, tts TEXT NOT NULL DEFAULT 'gemini-studio',
    genero TEXT, idioma TEXT NOT NULL DEFAULT 'es', estado TEXT NOT NULL DEFAULT 'pendiente', intentos INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '', salida TEXT NOT NULL DEFAULT '',
    inicio REAL NOT NULL DEFAULT 0, fin REAL NOT NULL DEFAULT 0, latido REAL NOT NULL DEFAULT 0
);
"""
ESTADOS = ("pendiente", "en_proceso", "hecho", "error")


@dataclass
class Trabajo:
    id: str
    lote: str = ""
    personaje: str = "profesor"
    audio: Optional[str] = None
    guion: Optional[str] = None
    poses: str = ""
    escenarios: str = ""
    resolucion: str = "1280x720"
    semilla: Optional[int] = None
    tts: str = "gemini-studio"
    genero: Optional[str] = None
    idioma: str = "es"                 # es | en | mixto: decide el reconocedor de visemas (FR-021)
    estado: str = "pendiente"
    intentos: int = 0
    error: str = ""
    salida: str = ""
    inicio: float = 0.0
    fin: float = 0.0
    latido: float = 0.0


_CAMPOS = [f.name for f in fields(Trabajo)]
_CAMPOS_ENCOLAR = ["id", "lote", "personaje", "audio", "guion", "poses", "escenarios", "resolucion",
                   "semilla", "tts", "genero", "idioma"]


class Cola:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(ESQUEMA)
            columnas = {f["name"] for f in con.execute("PRAGMA table_info(trabajos)")}
            if "idioma" not in columnas:                     # cola creada antes de existir el idioma por clase
                con.execute("ALTER TABLE trabajos ADD COLUMN idioma TEXT NOT NULL DEFAULT 'es'")

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.ruta, timeout=60, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=60000")
        try:
            yield con
        finally:
            con.close()

    @staticmethod
    def _a_trabajo(fila: sqlite3.Row) -> Trabajo:
        return Trabajo(**{c: fila[c] for c in _CAMPOS})

    # ---- altas ----
    def encolar(self, trabajos: List[Trabajo]) -> Tuple[int, List[str]]:
        """Devuelve (nuevos, ids duplicados que se ignoraron)."""
        nuevos, duplicados = 0, []
        with self._conexion() as con:
            con.execute("BEGIN IMMEDIATE")
            for t in trabajos:
                cur = con.execute(
                    f"INSERT OR IGNORE INTO trabajos ({','.join(_CAMPOS_ENCOLAR)}) "
                    f"VALUES ({','.join('?' * len(_CAMPOS_ENCOLAR))})",
                    [getattr(t, c) for c in _CAMPOS_ENCOLAR])
                if cur.rowcount:
                    nuevos += 1
                else:
                    duplicados.append(t.id)
            con.execute("COMMIT")
        return nuevos, duplicados

    # ---- ciclo de vida ----
    def reclamar(self, lote: Optional[str] = None) -> Optional[Trabajo]:
        with self._conexion() as con:
            con.execute("BEGIN IMMEDIATE")
            filtro, args = ("AND lote = ?", [lote]) if lote else ("", [])
            fila = con.execute(f"SELECT * FROM trabajos WHERE estado = 'pendiente' {filtro} "
                               "ORDER BY orden LIMIT 1", args).fetchone()
            if fila is None:
                con.execute("COMMIT")
                return None
            ahora = time.time()
            con.execute("UPDATE trabajos SET estado='en_proceso', inicio=?, latido=?, fin=0, error='' WHERE id=?",
                        (ahora, ahora, fila["id"]))
            con.execute("COMMIT")
        t = self._a_trabajo(fila)
        t.estado, t.inicio, t.latido = "en_proceso", ahora, ahora
        return t

    def latido(self, id_trabajo: str) -> None:
        with self._conexion() as con:
            con.execute("UPDATE trabajos SET latido=? WHERE id=? AND estado='en_proceso'", (time.time(), id_trabajo))

    def terminar(self, id_trabajo: str, salida: str) -> None:
        with self._conexion() as con:
            con.execute("UPDATE trabajos SET estado='hecho', salida=?, fin=?, error='' WHERE id=?",
                        (str(salida), time.time(), id_trabajo))

    def fallar(self, id_trabajo: str, causa: str) -> None:
        with self._conexion() as con:
            con.execute("UPDATE trabajos SET estado='error', error=?, fin=?, intentos=intentos+1 WHERE id=?",
                        (causa, time.time(), id_trabajo))

    def recuperar_huerfanos(self, max_edad_s: float) -> List[str]:
        """Los 'en_proceso' sin latido reciente (el proceso murió) vuelven a 'pendiente'."""
        limite = time.time() - max_edad_s
        with self._conexion() as con:
            con.execute("BEGIN IMMEDIATE")
            ids = [f["id"] for f in con.execute(
                "SELECT id FROM trabajos WHERE estado='en_proceso' AND latido < ?", (limite,))]
            con.execute("UPDATE trabajos SET estado='pendiente' WHERE estado='en_proceso' AND latido < ?", (limite,))
            con.execute("COMMIT")
        return ids

    def reintentar_errores(self, lote: Optional[str] = None) -> int:
        filtro, args = ("AND lote = ?", [lote]) if lote else ("", [])
        with self._conexion() as con:
            return con.execute(f"UPDATE trabajos SET estado='pendiente', error='' WHERE estado='error' {filtro}",
                               args).rowcount

    # ---- consultas ----
    def trabajos(self, estado: Optional[str] = None, lote: Optional[str] = None) -> List[Trabajo]:
        condiciones, args = [], []
        if estado:
            condiciones.append("estado = ?"); args.append(estado)
        if lote:
            condiciones.append("lote = ?"); args.append(lote)
        donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
        with self._conexion() as con:
            return [self._a_trabajo(f) for f in con.execute(f"SELECT * FROM trabajos {donde} ORDER BY orden", args)]

    def resumen(self, lote: Optional[str] = None) -> dict:
        filtro, args = ("WHERE lote = ?", [lote]) if lote else ("", [])
        r = {e: 0 for e in ESTADOS}
        with self._conexion() as con:
            for f in con.execute(f"SELECT estado, COUNT(*) AS n FROM trabajos {filtro} GROUP BY estado", args):
                r[f["estado"]] = f["n"]
        r["total"] = sum(r[e] for e in ESTADOS)
        return r

    def _forzar_latido(self, id_trabajo: str, marca: float) -> None:     # solo para pruebas
        with self._conexion() as con:
            con.execute("UPDATE trabajos SET latido=? WHERE id=?", (marca, id_trabajo))
