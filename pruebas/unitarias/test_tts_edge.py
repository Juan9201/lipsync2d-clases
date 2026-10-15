"""FR-010: proveedor edge con la biblioteca simulada (sin red)."""
import sys
import types

import pytest

from src.errores import TTSNoDisponible
from src.tts.base import OpcionesTTS


def test_edge_sin_internet_sugiere_piper(proyecto_tmp, monkeypatch):
    modulo = types.ModuleType("edge_tts")

    class Comunicar:
        def __init__(self, texto, voz, **kw):
            pass

        async def save(self, ruta):
            raise OSError("sin conexión")

    modulo.Communicate = Comunicar
    monkeypatch.setitem(sys.modules, "edge_tts", modulo)
    from src.tts.edge import ProveedorEdge
    with pytest.raises(TTSNoDisponible) as exc:
        ProveedorEdge().sintetizar("Hola.", proyecto_tmp / "a.mp3", OpcionesTTS())
    assert "--audio" in str(exc.value) and "piper" not in str(exc.value)


def test_edge_guarda_el_audio(proyecto_tmp, monkeypatch):
    modulo = types.ModuleType("edge_tts")
    vistos = {}

    class Comunicar:
        def __init__(self, texto, voz, **kw):
            vistos.update(texto=texto, voz=voz)

        async def save(self, ruta):
            open(ruta, "wb").write(b"mp3")

    modulo.Communicate = Comunicar
    monkeypatch.setitem(sys.modules, "edge_tts", modulo)
    from src.tts.edge import ProveedorEdge
    destino = proyecto_tmp / "clases" / "e.mp3"
    destino.parent.mkdir(exist_ok=True)
    ProveedorEdge().sintetizar("Hola.", destino, OpcionesTTS(voz="es-MX-JorgeNeural"))
    assert destino.read_bytes() == b"mp3" and vistos == {"texto": "Hola.", "voz": "es-MX-JorgeNeural"}
