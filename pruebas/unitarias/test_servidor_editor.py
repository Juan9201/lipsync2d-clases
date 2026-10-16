"""El servidor del Editor de poses guarda la calibración en disco sin perder versiones anteriores."""
import importlib.util
import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[2] / "prototipos" / "editor" / "servidor_editor.py"


@pytest.fixture
def srv(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("servidor_editor", RUTA)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "CALIBRACIONES", tmp_path / "cal")
    monkeypatch.setattr(m, "HISTORIAL", tmp_path / "cal" / "historial")
    return m


def test_guarda_y_conserva_la_version_anterior(srv):
    assert srv.guardar_con_historial("calibracion_frontal.json", b'{"a":1}') is True
    assert srv.guardar_con_historial("calibracion_frontal.json", b'{"a":2}') is True
    assert (srv.CALIBRACIONES / "calibracion_frontal.json").read_bytes() == b'{"a":2}'
    copias = list(srv.HISTORIAL.glob("calibracion_frontal-*.json"))
    assert len(copias) == 1 and copias[0].read_bytes() == b'{"a":1}'


def test_si_no_cambia_no_crea_copia(srv):
    srv.guardar_con_historial("estado_completo.json", b"{}")
    assert srv.guardar_con_historial("estado_completo.json", b"{}") is False
    assert not srv.HISTORIAL.exists() or not list(srv.HISTORIAL.glob("*.json"))


@pytest.mark.parametrize("nombre", ["../fuera.json", "a/b.json", "x.py", "con espacio.json", ".json", "..\\x.json"])
def test_rechaza_nombres_peligrosos(srv, nombre):
    with pytest.raises(ValueError):
        srv.guardar_con_historial(nombre, b"{}")


def test_limita_el_historial(srv, monkeypatch):
    import os
    monkeypatch.setattr(srv, "COPIAS_POR_ARCHIVO", 3)
    destino = srv.CALIBRACIONES / "calibracion_x.json"
    for i in range(8):
        srv.guardar_con_historial("calibracion_x.json", str(i).encode())
        os.utime(destino, (1_700_000_000 + i * 10, 1_700_000_000 + i * 10))      # cada versión con su propio sello
    copias = sorted(srv.HISTORIAL.glob("calibracion_x-*.json"))
    assert len(copias) == 3
    assert [c.read_bytes() for c in copias] == [b"4", b"5", b"6"]               # las 3 versiones previas más recientes; la 7 es la actual


def test_el_endpoint_http_guarda_y_rechaza(srv):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(srv.Manejador, directory=str(srv.CALIBRACIONES.parent)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        puerto = httpd.server_address[1]
        ok = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{puerto}/guardar/calibracion_frontal.json",
                                                           data=b'{"v":5}', method="POST"))
        assert ok.status == 200 and (srv.CALIBRACIONES / "calibracion_frontal.json").read_bytes() == b'{"v":5}'
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{puerto}/guardar/..%2Fmalo.json",
                                                          data=b"{}", method="POST"))
        assert exc.value.code in (400, 404)
    finally:
        httpd.shutdown()
