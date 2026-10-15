"""Opción de género (hombre/mujer): elige la voz de cada proveedor desde tts.yaml."""
import pytest
import yaml

from src.errores import TTSNoDisponible
from src.tts import obtener_proveedor

CONFIG = {
    "genero": "hombre",
    "gemini-studio": {"url": "http://127.0.0.1:5055", "idioma": "es-ES",
                      "voces": {"hombre": "Puck", "mujer": "Kore"}},
    "edge": {"voces": {"hombre": "en-US-AndrewMultilingualNeural", "mujer": "en-US-AvaMultilingualNeural"}},
}


@pytest.fixture
def raiz(proyecto_tmp):
    (proyecto_tmp / "tts.yaml").write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    return proyecto_tmp


def test_por_defecto_usa_el_genero_del_archivo(raiz):
    _, op = obtener_proveedor("gemini-studio", raiz)
    assert op.voz == "Puck" and op.idioma == "es-ES"
    prov, op = obtener_proveedor("edge", raiz)
    assert op.voz == "en-US-AndrewMultilingualNeural"


def test_el_parametro_genero_manda_sobre_el_archivo(raiz):
    _, op = obtener_proveedor("gemini-studio", raiz, genero="mujer")
    assert op.voz == "Kore"
    prov, op = obtener_proveedor("edge", raiz, genero="mujer")
    assert op.voz == "en-US-AvaMultilingualNeural"


def test_sin_genero_en_el_archivo_el_defecto_es_hombre(proyecto_tmp):
    cfg = dict(CONFIG)
    del cfg["genero"]
    (proyecto_tmp / "tts.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _, op = obtener_proveedor("gemini-studio", proyecto_tmp)
    assert op.voz == "Puck"


def test_voz_explicita_tiene_prioridad_sobre_el_genero(proyecto_tmp):
    cfg = {"gemini-studio": {"voz": "Charon", "voces": {"hombre": "Puck", "mujer": "Kore"}}}
    (proyecto_tmp / "tts.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _, op = obtener_proveedor("gemini-studio", proyecto_tmp, genero="mujer")
    assert op.voz == "Charon"


def test_genero_invalido_explica_que_hacer(raiz):
    with pytest.raises(TTSNoDisponible) as exc:
        obtener_proveedor("edge", raiz, genero="robot")
    assert "hombre" in str(exc.value) and "mujer" in str(exc.value) and "Qué hacer" in str(exc.value)


def test_sin_archivo_usa_valores_por_defecto_de_hombre(proyecto_tmp):
    prov, op = obtener_proveedor("edge", proyecto_tmp)
    assert op.voz and "Andrew" in op.voz


def test_piper_ya_no_es_un_proveedor_valido(raiz):
    with pytest.raises(TTSNoDisponible) as exc:
        obtener_proveedor("piper", raiz)
    assert "gemini-studio" in str(exc.value)


def test_voz_por_defecto_de_hombre_en_gemini_es_podcaster_3(proyecto_tmp):
    _, op = obtener_proveedor("gemini-studio", proyecto_tmp)
    assert op.voz == "es-419-podcaster-3"
