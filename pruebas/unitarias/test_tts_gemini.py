"""FR-010, FR-013: proveedor gemini-studio contra un servidor HTTP falso de la webapp."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.errores import TTSNoDisponible
from src.tts.base import OpcionesTTS, TTSReintentable
from src.tts.gemini_studio import ProveedorGeminiStudio

AUDIO = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 64


class _Estado:
    health = {"ok": True, "has_key": True, "models": ["m"], "output_dir": "x"}
    generar = (200, {"file": "tts_001.mp3", "url": "/api/audio/tts_001.mp3"})
    peticiones: list = []


@pytest.fixture
def servidor():
    _Estado.health = {"ok": True, "has_key": True, "models": ["m"], "output_dir": "x"}
    _Estado.generar = (200, {"file": "tts_001.mp3", "url": "/api/audio/tts_001.mp3"})
    _Estado.peticiones = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, codigo, cuerpo):
            datos = json.dumps(cuerpo).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            if self.path == "/api/health":
                self._json(200, _Estado.health)
            elif self.path.startswith("/api/audio/"):
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(AUDIO)))
                self.end_headers()
                self.wfile.write(AUDIO)
            else:
                self._json(404, {"error": "no existe"})

        def do_POST(self):
            largo = int(self.headers.get("Content-Length", 0))
            _Estado.peticiones.append((self.path, json.loads(self.rfile.read(largo))))
            codigo, cuerpo = _Estado.generar
            self._json(codigo, cuerpo)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_genera_y_descarga_el_mp3(servidor, proyecto_tmp):
    prov = ProveedorGeminiStudio(servidor)
    destino = proyecto_tmp / "clases" / "clase ñ.mp3"
    destino.parent.mkdir(exist_ok=True)
    assert prov.sintetizar("Hola mundo.", destino, OpcionesTTS(voz="Puck", idioma="en-US")) == destino
    assert destino.read_bytes() == AUDIO
    ruta, cuerpo = _Estado.peticiones[0]
    assert ruta == "/api/generate-tts"
    assert cuerpo["text"] == "Hola mundo." and cuerpo["voice"] == "Puck" and cuerpo["language"] == "en-US"


def test_sin_opciones_no_envia_campos_vacios(servidor, proyecto_tmp):
    ProveedorGeminiStudio(servidor).sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
    cuerpo = _Estado.peticiones[0][1]
    assert set(cuerpo) <= {"text", "temperature", "speed", "pitch"}   # voz/idioma/modelo los pone la webapp


def test_comprobar_ok_y_sin_key(servidor):
    assert ProveedorGeminiStudio(servidor).comprobar().ok
    _Estado.health = dict(_Estado.health, has_key=False)
    estado = ProveedorGeminiStudio(servidor).comprobar()
    assert not estado.ok and "API key" in estado.detalle


def test_cuota_agotada_es_reintentable_con_causa_y_alternativas(servidor, proyecto_tmp):
    _Estado.generar = (429, {"error": "Has alcanzado el límite de cuota."})
    with pytest.raises(TTSReintentable) as exc:
        ProveedorGeminiStudio(servidor).sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
    assert "cuota" in str(exc.value).lower() and "--audio" in str(exc.value)


def test_error_400_no_se_reintenta(servidor, proyecto_tmp):
    _Estado.generar = (400, {"error": "Petición rechazada"})
    with pytest.raises(TTSNoDisponible) as exc:
        ProveedorGeminiStudio(servidor).sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
    assert not isinstance(exc.value, TTSReintentable)


def test_sin_key_en_la_webapp_explica_que_hacer(servidor, proyecto_tmp):
    _Estado.generar = (401, {"error": "No hay API key."})
    with pytest.raises(TTSNoDisponible) as exc:
        ProveedorGeminiStudio(servidor).sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
    assert "API key" in str(exc.value) and "Qué hacer" in str(exc.value)


def test_webapp_apagada(proyecto_tmp):
    prov = ProveedorGeminiStudio("http://127.0.0.1:9")
    with pytest.raises(TTSNoDisponible) as exc:
        prov.sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
    msg = str(exc.value)
    assert "5055" in msg or "127.0.0.1" in msg
    assert "--audio" in msg and "piper" not in msg
    assert not prov.comprobar().ok


def test_respuesta_sin_archivo(servidor, proyecto_tmp):
    _Estado.generar = (200, {"ok": True})
    with pytest.raises(TTSNoDisponible):
        ProveedorGeminiStudio(servidor).sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())


def test_timeout_de_la_webapp_es_reintentable_no_webapp_apagada(proyecto_tmp):
    """Una respuesta que tarda demasiado es transitoria: se reintenta, no se declara 'apagada'."""
    import time

    class Lento(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            time.sleep(1.0)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Lento)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        prov = ProveedorGeminiStudio(f"http://127.0.0.1:{httpd.server_address[1]}", timeout_s=0.2)
        with pytest.raises(TTSReintentable) as exc:
            prov.sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
        assert "tard" in str(exc.value).lower() and "--audio" in str(exc.value)
    finally:
        httpd.shutdown()
