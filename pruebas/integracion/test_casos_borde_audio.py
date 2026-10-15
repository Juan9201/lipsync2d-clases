"""Casos borde de audio (NFR-006, FR-011): silencios, frecuencias distintas, guion vacío o ausente."""
import pytest

from pruebas.utiles import EJEMPLO, FFMPEG, concatenar, duracion, recodificar, recortar_audio, silencio
from src.audio import convertir_para_analisis
from src.errores import AssetInvalido
from src.lipsync import analizar
from src.render import ParametrosRender, renderizar

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and EJEMPLO.exists()), reason="faltan ffmpeg o el audio de ejemplo")]


def _habla(proyecto, nombre="habla.mp3", seg=6):
    return recortar_audio(EJEMPLO, proyecto / "clases" / nombre, seg, inicio=20)


def test_silencio_largo_al_inicio_y_al_final(proyecto_con_assets):
    p = proyecto_con_assets
    audio = concatenar([silencio(p / "cache" / "s1.mp3", 6), _habla(p, "h.mp3", 4), silencio(p / "cache" / "s2.mp3", 6)],
                       p / "clases" / "con silencios.mp3")
    final = renderizar(ParametrosRender(personaje="profe", audio=audio), raiz=p)
    assert abs(duracion(final) - duracion(audio)) < 0.15


def test_un_audio_en_silencio_solo_produce_reposo(proyecto_con_assets):
    p = proyecto_con_assets
    mudo = silencio(p / "cache" / "mudo.mp3", 5)
    wav = convertir_para_analisis(mudo, p / "cache" / "mudo.wav")
    res = analizar(wav, cache_dir=p / "cache")
    assert {c.valor for c in res.cues} == {"X"}


@pytest.mark.parametrize("rate,canales", [(22050, 1), (48000, 2), (16000, 1)])
def test_mp3_con_otra_frecuencia_o_estereo(proyecto_con_assets, rate, canales):
    p = proyecto_con_assets
    audio = recodificar(_habla(p, "orig.mp3", 5), p / "clases" / f"r{rate}_{canales}.mp3", rate, canales)
    final = renderizar(ParametrosRender(personaje="profe", audio=audio), raiz=p)
    assert abs(duracion(final) - duracion(audio)) < 0.15


def test_guion_vacio_o_solo_con_etiquetas_se_trata_como_sin_guion(proyecto_con_assets, caplog):
    import logging
    p = proyecto_con_assets
    guion = p / "clases" / "solo etiquetas.txt"
    guion.write_text("[pose:P1] [toma:E1,P1,PL2]", encoding="utf-8")
    with caplog.at_level(logging.INFO):
        final = renderizar(ParametrosRender(personaje="profe", audio=_habla(p), guion=guion), raiz=p)
    assert final.exists() and any("sin guion" in r.getMessage().lower() for r in caplog.records)


def test_audio_danado_da_error_en_espanol(proyecto_con_assets):
    p = proyecto_con_assets
    malo = p / "clases" / "malo.mp3"
    malo.write_bytes(b"esto no es un mp3")
    with pytest.raises(AssetInvalido) as exc:
        renderizar(ParametrosRender(personaje="profe", audio=malo), raiz=p)
    assert "Qué hacer" in str(exc.value)
    assert not list((p / "salidas").glob("*.mp4"))
