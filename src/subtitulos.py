"""Cliente de la herramienta de subtítulos («Edición de video por lotes», http://127.0.0.1:3003; su API está en el 8001).

Manda un video, espera a que termine (corta silencios, Whisper, corrección, alineado, quemado) y baja el «Video con subtítulos» y su `.srt`.
Usa la pista de español con `mixed=true`: lo dicho se subtitula tal cual y cada frase lleva el color de su idioma (español verde, inglés azul).
Una sola pasada, sin traducir la clase al inglés.

El estilo se puede cambiar en `subtitulos.yaml` (raíz del proyecto); lo que no se indique conserva el valor de abajo.
"""
import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

import yaml

from src.errores import ErrorAccionable

API = "http://127.0.0.1:8001"
ESTILO_DEFECTO: Dict[str, str] = {
    "preset": "highlight",                         # Resalte
    "font": "HankenGrotesk-VariableFont_wght",
    "size": "md",
    "position": "bottom",
    "text_color": "#FFFFFF",
    "highlight_color": "#FFE14A",
    "es_text_color": "#FFFFFF", "es_highlight_color": "#22C55E",   # español: verde
    "en_text_color": "#FFFFFF", "en_highlight_color": "#0094FF",   # inglés: azul
}
SONDEO_S = 3.0
LIMITE_S = 3 * 3600


def cargar_estilo(raiz: Path) -> Dict[str, str]:
    estilo = dict(ESTILO_DEFECTO)
    ruta = Path(raiz) / "subtitulos.yaml"
    if ruta.is_file():
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        if not isinstance(datos, dict):
            raise ErrorAccionable(f"{ruta.name} debe ser un diccionario YAML", "Usa claves como preset, font, size, position")
        estilo.update({str(k): str(v) for k, v in datos.items()})
    return estilo


def _multipart(campos: Dict[str, str], archivo: Path):
    frontera = uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        partes.append(f'--{frontera}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
    tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
    partes.append(f'--{frontera}\r\nContent-Disposition: form-data; name="files"; filename="{archivo.name}"\r\n'
                  f"Content-Type: {tipo}\r\n\r\n".encode("utf-8"))
    partes.append(archivo.read_bytes())
    partes.append(f"\r\n--{frontera}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={frontera}"


def _pedir(url: str, datos: Optional[bytes] = None, cabeceras: Optional[dict] = None, espera: float = 60):
    req = urllib.request.Request(url, data=datos, headers=cabeceras or {})
    try:
        with urllib.request.urlopen(req, timeout=espera) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        return exc
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        raise ErrorAccionable(f"No responde la herramienta de subtítulos ({API}): {exc}",
                              "Ábrela con el acceso «Subtitulos animados» o con start-preview.ps1 y vuelve a intentarlo") from exc


def _json(url: str, datos: Optional[bytes] = None, cabeceras: Optional[dict] = None) -> dict:
    r = _pedir(url, datos, cabeceras)
    if isinstance(r, urllib.error.HTTPError):
        detalle = r.read().decode("utf-8", "replace")[:300]
        raise ErrorAccionable(f"La herramienta de subtítulos rechazó la petición ({r.code}): {detalle}", "Revisa el video y el estilo")
    return json.loads(r.decode("utf-8"))


def subtitular(video: Path, destino: Path, nombre: str, raiz: Path, al_avanzar: Optional[Callable[[str], None]] = None,
               api: str = API) -> Dict[str, Path]:
    """Sube `video`, espera y deja en `destino` `<nombre>_subtitulado.mp4` y `<nombre>_subtitulos.srt`. Devuelve sus rutas."""
    video, destino = Path(video), Path(destino)
    if not video.is_file() or video.stat().st_size == 0:
        raise ErrorAccionable(f"No existe el video {video}", "Comprueba que la clase terminó de renderizarse")
    aviso = al_avanzar or (lambda _t: None)
    campos = {**cargar_estilo(raiz), "track": "es", "mixed": "true", "mode": "auto", "lang_colors": "true"}
    cuerpo, tipo = _multipart(campos, video)
    job = _json(f"{api}/api/jobs", cuerpo, {"Content-Type": tipo})
    job_id, file_id = job["job_id"], job["items"][0]["file_id"]
    aviso("en la cola de la herramienta")
    inicio, ultimo, ultimo_aviso = time.time(), "", 0.0
    while True:
        item = _json(f"{api}/api/jobs/{job_id}")["items"][0]
        if item["status"] == "error":
            raise ErrorAccionable(f"La herramienta de subtítulos falló con {video.name}: {item.get('error') or item.get('detail')}",
                                  "Mira sus logs en http://127.0.0.1:3003 y reintenta")
        if item["status"] == "done":
            break
        estado = f"{item['status']}: {item.get('detail') or ''}".strip()
        if estado != ultimo or time.time() - ultimo_aviso > 20:        # también un latido, para que la interfaz no lo dé por caído
            aviso(estado)
            ultimo, ultimo_aviso = estado, time.time()
        if time.time() - inicio > LIMITE_S:
            raise ErrorAccionable(f"La herramienta de subtítulos tardó más de {LIMITE_S // 60} min con {video.name}", "Revisa que no esté atascada")
        time.sleep(SONDEO_S)
    destino.mkdir(parents=True, exist_ok=True)
    salida = {}
    for clave, sufijo, nombre_api in (("video", "_subtitulado.mp4", "video-es"), ("srt", "_subtitulos.srt", "srt-es")):
        datos = _pedir(f"{api}/api/jobs/{job_id}/files/{file_id}/{nombre_api}", espera=600)
        if isinstance(datos, urllib.error.HTTPError) or not datos:
            raise ErrorAccionable(f"No se pudo bajar {nombre_api} de {video.name}", "Reintenta la clase")
        ruta = destino / f"{nombre}{sufijo}"
        ruta.with_suffix(ruta.suffix + ".part").write_bytes(datos)
        ruta.with_suffix(ruta.suffix + ".part").replace(ruta)
        salida[clave] = ruta
    return salida
