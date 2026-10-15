"""FR-011: lectura/validación de audio y conversión para el análisis (necesita ffmpeg)."""
import subprocess
from pathlib import Path

import pytest

from src.audio import convertir_para_analisis, info_audio
from src.errores import AssetInvalido

RAIZ = Path(__file__).resolve().parents[2]
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"

pytestmark = pytest.mark.skipif(not FFMPEG.exists(), reason="ffmpeg no instalado (ejecuta instalar.ps1)")


def _generar(destino: Path, seg=1.0, rate=44100, fmt_extra=()):
    subprocess.run([str(FFMPEG), "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={seg}:sample_rate={rate}",
                    "-ac", "1", *fmt_extra, str(destino)], check=True)


def test_info_de_mp3_y_wav(proyecto_tmp):
    mp3 = proyecto_tmp / "clases" / "voz ñ.mp3"
    wav = proyecto_tmp / "clases" / "voz.wav"
    _generar(mp3, 2.0, 44100)
    _generar(wav, 1.0, 22050)
    i_mp3, i_wav = info_audio(mp3), info_audio(wav)
    assert abs(i_mp3.duracion_s - 2.0) < 0.15 and i_mp3.sample_rate == 44100 and i_mp3.formato == "mp3"
    assert abs(i_wav.duracion_s - 1.0) < 0.05 and i_wav.sample_rate == 22050 and i_wav.formato == "wav"


def test_convertir_para_analisis_wav_16k_mono(proyecto_tmp):
    mp3 = proyecto_tmp / "clases" / "voz.mp3"
    _generar(mp3, 1.5, 48000)
    destino = proyecto_tmp / "cache" / "análisis.wav"
    convertir_para_analisis(mp3, destino)
    info = info_audio(destino)
    assert info.sample_rate == 16000 and info.canales == 1 and info.formato == "wav"
    assert abs(info.duracion_s - 1.5) < 0.1


def test_archivo_inexistente(proyecto_tmp):
    with pytest.raises(AssetInvalido) as exc:
        info_audio(proyecto_tmp / "no_existe.mp3")
    assert "no existe" in str(exc.value).lower()


def test_archivo_corrupto(proyecto_tmp):
    malo = proyecto_tmp / "clases" / "malo.mp3"
    malo.write_bytes(b"esto no es audio")
    with pytest.raises(AssetInvalido) as exc:
        info_audio(malo)
    assert "Qué hacer" in str(exc.value)


def test_extension_no_soportada(proyecto_tmp):
    otro = proyecto_tmp / "clases" / "voz.ogg"
    otro.write_bytes(b"x")
    with pytest.raises(AssetInvalido) as exc:
        info_audio(otro)
    assert "MP3" in str(exc.value) and "WAV" in str(exc.value)
