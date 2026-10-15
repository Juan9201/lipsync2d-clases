"""Proveedor `gemini-studio`: cliente HTTP delgado de la webapp local gemini-tts-studio.
No importa ni modifica su código y no maneja la API key (la webapp ya la tiene)."""
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from src import rutas
from src.errores import TTSNoDisponible
from src.tts.base import EstadoProveedor, OpcionesTTS, TTSReintentable
from src.tts.candado import CandadoArchivo

URL_DEFECTO = "http://127.0.0.1:5055"
ALTERNATIVAS = "entrega un audio propio con --audio"
# La webapp numera los archivos listando su carpeta: no es segura ante peticiones simultáneas.
_CANDADO = threading.Lock()


class ProveedorGeminiStudio:
    nombre = "gemini-studio"
    extension = "mp3"
    limite_caracteres = 8000      # límite de la webapp por petición
    max_reintentos = 5

    def __init__(self, url: str = URL_DEFECTO, timeout_s: float = 300.0):
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s

    # ---- HTTP ----
    def _pedir(self, ruta: str, cuerpo: Optional[dict] = None, binario: bool = False):
        peticion = urllib.request.Request(
            self.url + ruta, method="POST" if cuerpo is not None else "GET",
            data=None if cuerpo is None else json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=self.timeout_s) as r:
                datos = r.read()
        except urllib.error.HTTPError as exc:
            raise self._error_http(exc) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise TTSReintentable(
                f"gemini-tts-studio tardó más de {self.timeout_s:.0f} s en responder",
                f"Vuelve a intentarlo, o {ALTERNATIVAS}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise TTSReintentable(
                    f"gemini-tts-studio tardó más de {self.timeout_s:.0f} s en responder",
                    f"Vuelve a intentarlo, o {ALTERNATIVAS}") from exc
            raise TTSNoDisponible(
                f"No se pudo conectar con gemini-tts-studio en {self.url}",
                f"Inicia la webapp (start.bat en su carpeta), o {ALTERNATIVAS}") from exc
        except (ConnectionError, OSError) as exc:
            raise TTSNoDisponible(
                f"No se pudo conectar con gemini-tts-studio en {self.url}",
                f"Inicia la webapp (start.bat en su carpeta), o {ALTERNATIVAS}") from exc
        return datos if binario else json.loads(datos.decode("utf-8"))

    def _error_http(self, exc: urllib.error.HTTPError) -> TTSNoDisponible:
        try:
            detalle = json.loads(exc.read().decode("utf-8")).get("error", "")
        except (ValueError, OSError):
            detalle = ""
        if exc.code == 401:
            return TTSNoDisponible(f"La webapp rechazó la API key de Gemini ({detalle or 'sin detalle'})",
                                   "Revisa la API key en el .env de gemini-tts-studio o en su panel")
        if exc.code == 429:
            return TTSReintentable(
                f"Se alcanzó el límite de cuota de Gemini ({detalle or 'sin detalle'})",
                f"Espera al reinicio de la cuota, o {ALTERNATIVAS}")
        if exc.code >= 500:
            return TTSReintentable(f"Error temporal de la API de Gemini ({exc.code}: {detalle or 'sin detalle'})",
                                   f"Vuelve a intentarlo en unos minutos, o {ALTERNATIVAS}")
        return TTSNoDisponible(f"La webapp rechazó la petición ({exc.code}: {detalle or 'sin detalle'})",
                               f"Revisa la voz, el idioma y el modelo en tts.yaml, o {ALTERNATIVAS}")

    # ---- interfaz ----
    def comprobar(self) -> EstadoProveedor:
        try:
            estado = self._pedir("/api/health")
        except TTSNoDisponible as exc:
            return EstadoProveedor(False, exc.causa)
        if not estado.get("has_key"):
            return EstadoProveedor(False, "La webapp no tiene API key de Gemini")
        return EstadoProveedor(True, f"disponible en {self.url}")

    def sintetizar(self, texto: str, destino: Path, opciones: OpcionesTTS) -> Path:
        cuerpo = {"text": texto, "temperature": opciones.temperatura,
                  "speed": opciones.velocidad, "pitch": opciones.tono}
        for campo, valor in (("voice", opciones.voz), ("language", opciones.idioma),
                             ("model", opciones.modelo)):
            if valor:
                cuerpo[campo] = valor
        if opciones.estilo:
            cuerpo["style"] = opciones.estilo
        with _CANDADO, CandadoArchivo(rutas.RAIZ / "lote" / "tts.lock"):     # hilos y procesos
            respuesta = self._pedir("/api/generate-tts", cuerpo)
            archivo = respuesta.get("file")
            if not archivo:
                raise TTSNoDisponible("La webapp no devolvió ningún archivo de audio",
                                      f"Revisa su ventana de consola, o {ALTERNATIVAS}")
            audio = self._pedir(f"/api/audio/{archivo}", binario=True)
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(audio)
        return destino
