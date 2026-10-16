"""Servidor local del Editor de poses (solo 127.0.0.1).

Sirve la carpeta `prototipos/` y guarda en disco, apenas cambias algo, la calibración que el editor le envía:
  prototipos/editor/calibraciones/calibracion_<vista>.json   (lo que importa `importar-poses`)
  prototipos/editor/calibraciones/estado_completo.json       (todo, para reabrir el editor donde lo dejaste)
  prototipos/editor/calibraciones/historial/                 (copias con fecha de cada versión anterior)

Uso:  python prototipos/editor/servidor_editor.py [puerto]      (por defecto 8770)
"""
import os
import re
import sys
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROTOTIPOS = Path(__file__).resolve().parents[1]
CALIBRACIONES = Path(__file__).resolve().parent / "calibraciones"
HISTORIAL = CALIBRACIONES / "historial"
NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_\-]+\.json$")
MAX_BYTES = 8 * 1024 * 1024
COPIAS_POR_ARCHIVO = 200


def guardar_con_historial(nombre: str, datos: bytes) -> bool:
    """Escribe el archivo de forma atómica. Si ya existía y cambia, deja antes una copia con fecha."""
    if not NOMBRE_VALIDO.match(nombre):
        raise ValueError("nombre de archivo no válido")
    CALIBRACIONES.mkdir(parents=True, exist_ok=True)
    destino = CALIBRACIONES / nombre
    if destino.is_file():
        if destino.read_bytes() == datos:
            return False
        HISTORIAL.mkdir(parents=True, exist_ok=True)
        sello = time.strftime("%Y%m%d-%H%M%S", time.localtime(destino.stat().st_mtime))
        (HISTORIAL / f"{destino.stem}-{sello}.json").write_bytes(destino.read_bytes())
        copias = sorted(HISTORIAL.glob(f"{destino.stem}-*.json"))
        for vieja in copias[:-COPIAS_POR_ARCHIVO]:
            vieja.unlink()
    temporal = destino.with_suffix(".json.tmp")
    temporal.write_bytes(datos)
    os.replace(temporal, destino)
    return True


class Manejador(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        partes = self.path.strip("/").split("/")
        if len(partes) != 2 or partes[0] != "guardar":
            self.send_error(404)
            return
        largo = int(self.headers.get("Content-Length", 0))
        if largo <= 0 or largo > MAX_BYTES:
            self.send_error(413)
            return
        try:
            cambio = guardar_con_historial(partes[1], self.rfile.read(largo))
        except ValueError:
            self.send_error(400, "nombre no válido")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"guardado" if cambio else b"sin cambios")

    def log_message(self, formato, *args):
        if self.command == "POST":
            return                                  # no llenar la consola con cada autoguardado
        super().log_message(formato, *args)


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), partial(Manejador, directory=str(PROTOTIPOS)))
    print(f"Editor en http://localhost:{puerto}/editor/editor.html  (se guarda en {CALIBRACIONES})", flush=True)
    servidor.serve_forever()
