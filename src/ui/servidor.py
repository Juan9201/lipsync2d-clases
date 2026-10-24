"""Servidor HTTP de la interfaz local. Solo escucha en 127.0.0.1, rechaza peticiones con un Host ajeno (DNS rebinding) y exige
la cabecera X-Lipsync en todo lo que modifica algo (una web cualquiera no puede enviarla sin permiso del navegador)."""
import json
import mimetypes
import re
import shutil
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from src.errores import ErrorAccionable
from src.ui import logica
from src.ui.logica import Tareas

WEB = Path(__file__).resolve().parent / "web"
MAX_CUERPO = 40 * 1024 * 1024
MAX_SUBIDA = 2 * 1024 ** 3                       # un video de fondo puede ser grande
ARCHIVO_SEGURO = re.compile(r"^[\w\-. ]+\.(mp4|mp3|wav)$")


class Aplicacion:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.tareas = Tareas(self.raiz)


def crear_servidor(raiz: Path, puerto: int = 8780) -> ThreadingHTTPServer:
    app = Aplicacion(raiz)

    class Manejador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "Lipsync2D"

        # ---- utilidades ----
        def log_message(self, *a):
            pass

        def _permitido(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            puerto_real = self.server.server_address[1]
            return host in (f"127.0.0.1:{puerto_real}", f"localhost:{puerto_real}")

        def _json(self, datos, codigo: int = 200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _error(self, mensaje: str, codigo: int = 400):
            self._json({"error": mensaje}, codigo)

        def _leer_json(self) -> dict:
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > MAX_CUERPO:
                raise ErrorAccionable("El envío es demasiado grande", "Sube menos archivos a la vez")
            if not largo:
                return {}
            try:
                datos = json.loads(self.rfile.read(largo).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ErrorAccionable("La petición no es un JSON válido", "Recarga la página e inténtalo de nuevo") from exc
            return datos if isinstance(datos, dict) else {}

        def _archivo(self, ruta: Path, tipo: Optional[str] = None):
            """Entrega un archivo con soporte de Range (el reproductor de video lo necesita para saltar)."""
            if not ruta.is_file():
                return self._error("No existe ese archivo", 404)
            tamano = ruta.stat().st_size
            tipo = tipo or mimetypes.guess_type(str(ruta))[0] or "application/octet-stream"
            inicio, fin = 0, tamano - 1
            m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    inicio = int(m.group(1))
                    fin = int(m.group(2)) if m.group(2) else fin
                else:
                    inicio = max(0, tamano - int(m.group(2)))
                if inicio > fin or inicio >= tamano:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{tamano}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                fin = min(fin, tamano - 1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {inicio}-{fin}/{tamano}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(fin - inicio + 1))
            self.end_headers()
            with open(ruta, "rb") as f:
                f.seek(inicio)
                restante = fin - inicio + 1
                while restante > 0:
                    trozo = f.read(min(1024 * 256, restante))
                    if not trozo:
                        break
                    self.wfile.write(trozo)
                    restante -= len(trozo)

        # ---- GET ----
        def do_GET(self):
            if not self._permitido():
                return self._error("Host no permitido", 403)
            url = urlparse(self.path)
            ruta, consulta = unquote(url.path), parse_qs(url.query)
            try:
                if ruta in ("/", "/index.html"):
                    return self._archivo(WEB / "index.html", "text/html; charset=utf-8")
                if ruta in ("/app.js", "/app.css"):
                    return self._archivo(WEB / ruta[1:], "text/javascript; charset=utf-8" if ruta.endswith(".js") else "text/css; charset=utf-8")
                if ruta.startswith("/salidas/"):
                    nombre = ruta.split("/", 2)[2]
                    carpeta = app.raiz / "salidas"
                    if not ARCHIVO_SEGURO.match(nombre) or ".." in nombre:
                        return self._error("Archivo no válido", 404)
                    return self._archivo(carpeta / nombre)
                m = re.match(r"^/api/escenas/([^/]+)/config$", ruta)
                if m:
                    return self._json(logica.config_escena(app.raiz, m.group(1)))
                m = re.match(r"^/miniaturas/([^/]+)\.jpg$", ruta)
                if m:
                    return self._archivo(logica.miniatura_escenario(app.raiz, m.group(1)), "image/jpeg")
                if ruta == "/api/estado":
                    return self._json(logica.estado_recursos(app.raiz))
                if ruta == "/api/clases":
                    return self._json({"clases": logica.listar_clases(app.raiz), "siguiente_id": logica.siguiente_id(app.raiz)})
                m = re.match(r"^/api/clases/([^/]+)/texto$", ruta)
                if m:
                    return self._json({"texto": logica.leer_texto(app.raiz, m.group(1))})
                if ruta == "/api/tareas":
                    return self._json({"tareas": app.tareas.listar()})
                if ruta == "/api/lote":
                    return self._json(logica.estado_lote(app.raiz))
                if ruta == "/api/progreso":
                    return self._json(logica.progreso_en_vivo(app.raiz))
                return self._error("No existe esa página", 404)
            except ErrorAccionable as exc:
                return self._error(str(exc))
            except (BrokenPipeError, ConnectionResetError):
                return None

        # ---- POST ----
        def do_POST(self):
            if not self._permitido():
                return self._error("Host no permitido", 403)
            if self.headers.get("X-Lipsync") != "1":
                return self._error("Falta la cabecera de seguridad X-Lipsync", 403)
            url = urlparse(self.path)
            ruta = unquote(url.path)
            try:
                if ruta == "/api/escenarios":                          # subida binaria: el cuerpo es el archivo
                    return self._subir_escenario(parse_qs(url.query))
                m = re.match(r"^/api/escenas/([^/]+)/frente$", ruta)
                if m:
                    return self._subir_frente(m.group(1))
                d = self._leer_json()
                m = re.match(r"^/api/escenas/([^/]+)/config$", ruta)
                if m:
                    return self._json({"config": logica.guardar_escena(app.raiz, m.group(1), d.get("config") or {})})
                m = re.match(r"^/api/escenas/([^/]+)/vista$", ruta)
                if m:
                    imagen, v = logica.vista_escena(app.raiz, m.group(1), d.get("config") or {}, d.get("pose", ""), d.get("plano", "PL3"),
                                                    d.get("visema", "X"), d.get("ojos", "abierto"), bool(d.get("luz", True)),
                                                    bool(d.get("borrador", False)))
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(imagen)))
                    self.send_header("X-Ventana", ",".join(f"{x:.2f}" for x in v))
                    self.send_header("Access-Control-Expose-Headers", "X-Ventana")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(imagen)
                    return None
                campos = {k: d[k] for k in logica.CAMPOS_CLASE if k in d}
                if ruta == "/api/clases":
                    return self._json(logica.guardar_clase(app.raiz, d.get("texto", ""), d.get("id") or None, **campos))
                if ruta == "/api/clases/importar-carpeta":
                    from src.guiones_drive import importar_carpeta
                    return self._json(importar_carpeta(app.raiz, Path(str(d.get("carpeta") or "")), d.get("niveles") or None,
                                                       bool(d.get("solo_ia", True))))
                if ruta == "/api/clases/importar":
                    ids = logica.importar_guiones(app.raiz, d.get("archivos") or [], **campos)
                    return self._json({"ids": ids})
                m = re.match(r"^/api/clases/([^/]+)$", ruta)
                if m:
                    return self._json(logica.actualizar_clase(app.raiz, m.group(1), **({"texto": d["texto"]} if "texto" in d else {}), **campos))
                m = re.match(r"^/api/clases/([^/]+)/eliminar$", ruta)
                if m:
                    logica.eliminar_clase(app.raiz, m.group(1))
                    return self._json({"ok": True})
                m = re.match(r"^/api/escenarios/([^/]+)/eliminar$", ruta)
                if m:
                    logica.quitar_escenario(app.raiz, m.group(1))
                    return self._json({"ok": True})
                if ruta == "/api/voz/generar":
                    return self._json({"tarea": self._generar_voz(d)})
                if ruta == "/api/render":
                    cmd = logica.comando_render(app.raiz, d.get("id", ""), d.get("escenario", ""), bool(d.get("director", True)),
                                                d.get("plano", ""))
                    tid = app.tareas.lanzar_comando(f"Render de {d.get('id')}", cmd, d.get("id", ""), logica.salida_de_render)
                    return self._json({"tarea": tid})
                if ruta == "/api/salidas/abrir":
                    return self._json(logica.abrir_carpeta_salidas(app.raiz))
                if ruta == "/api/lote":
                    return self._json(logica.crear_lote(app.raiz, d.get("nombre", ""), d.get("ids") or []))
                if ruta == "/api/producir":
                    if any(t["estado"] == "en curso" and str(t["titulo"]).startswith("Lote") for t in app.tareas.listar()):
                        raise ErrorAccionable("Ya hay un lote corriendo", "Espera a que termine; su avance está en el panel «En vivo» de la pestaña Lote")
                    n = max(1, min(int(d.get("trabajadores") or 2), 4))
                    r = logica.preparar_produccion(app.raiz, d.get("ids") or [], str(d.get("escenario") or ""))
                    tid = app.tareas.lanzar_comando(f"Lote {r['lote']} · {r['encoladas'] + r['ya_estaban']} clases · {n} trabajadores",
                                                    [sys.executable, "-m", "src.lote", "correr", "--trabajadores", str(n)])
                    return self._json({**r, "tarea": tid, "trabajadores": n})
                if ruta == "/api/lote/correr":
                    n = max(1, min(int(d.get("trabajadores") or 2), 8))
                    tid = app.tareas.lanzar_comando(f"Lote con {n} trabajadores",
                                                    [sys.executable, "-m", "src.lote", "correr", "--trabajadores", str(n)])
                    return self._json({"tarea": tid})
                if ruta == "/api/lote/reintentar":
                    from src.lote.cola import Cola
                    return self._json({"reintentadas": Cola(app.raiz / "lote" / "cola.db").reintentar_errores()})
                return self._error("No existe esa acción", 404)
            except ErrorAccionable as exc:
                return self._error(str(exc))
            except (BrokenPipeError, ConnectionResetError):
                return None
            except Exception as exc:                                  # un fallo no debe tumbar el servidor
                return self._error(f"{type(exc).__name__}: {exc}", 500)

        def _subir_frente(self, carpeta: str):
            largo = int(self.headers.get("Content-Length") or 0)
            if largo <= 0 or largo > MAX_SUBIDA:
                raise ErrorAccionable("El archivo está vacío o es demasiado grande (máximo 2 GB)", "Elige otro archivo")
            temp = app.raiz / "cache" / "subidas"
            temp.mkdir(parents=True, exist_ok=True)
            destino = temp / f"frente_{time.time_ns()}.bin"
            try:
                with open(destino, "wb") as f:
                    restante = largo
                    while restante > 0:
                        trozo = self.rfile.read(min(1024 * 1024, restante))
                        if not trozo:
                            raise ErrorAccionable("La subida se cortó antes de terminar", "Vuelve a subir el archivo")
                        f.write(trozo)
                        restante -= len(trozo)
                return self._json(logica.subir_frente(app.raiz, carpeta, destino))
            finally:
                destino.unlink(missing_ok=True)
                try:
                    temp.rmdir()
                except OSError:
                    pass

        def _subir_escenario(self, consulta: dict):
            largo = int(self.headers.get("Content-Length") or 0)
            if largo <= 0 or largo > MAX_SUBIDA:
                raise ErrorAccionable("El archivo está vacío o es demasiado grande (máximo 2 GB)", "Elige otro archivo")
            nombre = (consulta.get("nombre") or [""])[0]
            archivo = (consulta.get("archivo") or [""])[0]
            reemplazar = (consulta.get("reemplazar") or [""])[0] or None
            temp = app.raiz / "cache" / "subidas"
            temp.mkdir(parents=True, exist_ok=True)
            destino = temp / f"subida_{time.time_ns()}.bin"
            try:
                with open(destino, "wb") as f:                           # se guarda por trozos: un video no cabe en memoria
                    restante = largo
                    while restante > 0:
                        trozo = self.rfile.read(min(1024 * 1024, restante))
                        if not trozo:
                            raise ErrorAccionable("La subida se cortó antes de terminar", "Vuelve a subir el archivo")
                        f.write(trozo)
                        restante -= len(trozo)
                extension = Path(archivo).suffix
                return self._json(logica.agregar_escenario(app.raiz, nombre or Path(archivo).stem, extension, destino, reemplazar))
            finally:
                destino.unlink(missing_ok=True)
                try:
                    temp.rmdir()
                except OSError:
                    pass

        def _generar_voz(self, d: dict) -> str:
            from src.cli import generar_voz
            id_clase = d.get("id", "")
            ficha = next((c for c in logica.listar_clases(app.raiz) if c["id"] == id_clase), None)
            if ficha is None:
                raise ErrorAccionable(f"No existe la clase «{id_clase}»", "Actualiza la lista")
            carpeta = app.raiz / "clases"
            if d.get("forzar") and ficha["audio"]:                    # cambiar de voz: el audio anterior va a la papelera
                papelera = carpeta / "_papelera"
                papelera.mkdir(exist_ok=True)
                shutil.move(str(carpeta / ficha["audio"]), str(papelera / f"{Path(ficha['audio']).stem}-{time.strftime('%Y%m%d-%H%M%S')}{Path(ficha['audio']).suffix}"))
            guion = carpeta / f"{id_clase}.txt"
            return app.tareas.lanzar_funcion(
                f"Voz de {id_clase}", lambda: generar_voz(guion, "gemini-studio", app.raiz, "hombre", ficha["idioma"], ficha["voz"]), id_clase)

    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    servidor.daemon_threads = True
    servidor.aplicacion = app
    return servidor
