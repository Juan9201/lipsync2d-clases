"""FR-012, FR-010, FR-013: limpieza de etiquetas, partición, reintentos y unión de audios."""
import re
import subprocess
from pathlib import Path

import pytest

from src.errores import TTSNoDisponible
from src.tts.base import TTSReintentable
from src.tts.comun import con_reintentos, limpiar_etiquetas, partir_texto, unir_audios

RAIZ = Path(__file__).resolve().parents[2]
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffprobe.exe"


def test_quita_solo_las_etiquetas_propias_y_conserva_las_del_tts():
    texto = "Hola [pose:P3] mundo [short pause] fin [TOMA:E1,P1,PL2]. [giggle] Listo [plano:PL4]"
    assert limpiar_etiquetas(texto) == "Hola mundo [short pause] fin. [giggle] Listo"


def test_conserva_los_saltos_de_linea():
    assert limpiar_etiquetas("Uno.\n\n[pose:P1] Dos.") == "Uno.\n\nDos."


def test_texto_sin_etiquetas_no_cambia():
    assert limpiar_etiquetas("Texto normal, con acentos: ¿qué tal?") == "Texto normal, con acentos: ¿qué tal?"


def test_partir_respeta_el_limite_y_no_pierde_texto():
    texto = ("Primera frase corta. Segunda frase un poco más larga que la primera. " * 3 +
             "\n\nOtro párrafo con varias oraciones. ¿Se parte bien? ¡Eso espero!")
    trozos = partir_texto(texto, 120)
    assert len(trozos) > 1 and all(0 < len(t) <= 120 for t in trozos)
    normal = lambda s: re.sub(r"\s+", " ", s).strip()
    assert normal(" ".join(trozos)) == normal(texto)


def test_texto_corto_es_un_solo_trozo():
    assert partir_texto("Hola mundo.", 8000) == ["Hola mundo."]


def test_frase_larga_sin_puntuacion_se_parte_en_espacios():
    texto = "palabra " * 100
    trozos = partir_texto(texto, 50)
    assert all(len(t) <= 50 for t in trozos) and len(trozos) > 1


def test_reintentos_con_espera_creciente():
    esperas, intentos = [], []

    def inestable():
        intentos.append(1)
        if len(intentos) < 3:
            raise TTSReintentable("cuota", "espera")
        return "ok"

    assert con_reintentos(inestable, max_intentos=5, espera_base=2, dormir=esperas.append,
                          aleatorio=lambda: 0.0) == "ok"
    assert esperas == [2, 4]


def test_agota_los_reintentos_y_explica():
    def siempre():
        raise TTSReintentable("Se alcanzó el límite de cuota", "Usa --tts piper")

    with pytest.raises(TTSNoDisponible) as exc:
        con_reintentos(siempre, max_intentos=3, espera_base=1, dormir=lambda s: None, aleatorio=lambda: 0.0)
    assert "cuota" in str(exc.value) and "3 intentos" in str(exc.value) and "piper" in str(exc.value)


def test_error_no_reintentable_sale_de_inmediato():
    llamadas = []

    def falla():
        llamadas.append(1)
        raise TTSNoDisponible("sin key", "añade la key")

    with pytest.raises(TTSNoDisponible):
        con_reintentos(falla, max_intentos=5, espera_base=1, dormir=lambda s: pytest.fail("no debe esperar"))
    assert len(llamadas) == 1


@pytest.mark.skipif(not FFMPEG.exists(), reason="ffmpeg no instalado")
def test_unir_audios_suma_las_duraciones(proyecto_tmp):
    partes = []
    for i, seg in enumerate((1.0, 1.5)):
        ruta = proyecto_tmp / "cache" / f"parte ñ {i}.mp3"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(FFMPEG), "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={seg}:sample_rate=44100", "-ac", "1",
                        "-b:a", "128k", str(ruta)], check=True)
        partes.append(ruta)
    destino = proyecto_tmp / "clases" / "unido.mp3"
    unir_audios(partes, destino, ffmpeg=FFMPEG)
    out = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(destino)], capture_output=True, text=True, check=True).stdout
    assert abs(float(out) - 2.5) < 0.15
