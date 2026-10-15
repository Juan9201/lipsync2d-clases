"""FR-031, FR-032, FR-033: codificador por streaming, escritura atómica (necesita ffmpeg)."""
import json
import subprocess
import wave
from pathlib import Path

import pytest

from src.encoder import Codificador
from src.errores import ErrorAccionable

RAIZ = Path(__file__).resolve().parents[2]
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffprobe.exe"

pytestmark = pytest.mark.skipif(not FFMPEG.exists(), reason="ffmpeg no instalado (ejecuta instalar.ps1)")

W, H, N = 128, 72, 50  # 2 s a 25 fps


def _wav(ruta: Path, seg=2.0):
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seg))
    return ruta


def _sonda(ruta):
    out = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(ruta)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _frame(i):
    return bytes([(i * 5) % 256, 80, 160]) * (W * H)


def test_render_correcto_produce_mp4_valido(proyecto_tmp):
    audio = _wav(proyecto_tmp / "cache" / "voz.wav")
    final = proyecto_tmp / "salidas" / "clase ñ_20261014.mp4"
    with Codificador(final, audio, W, H, fps=25, ffmpeg=FFMPEG, ffprobe=FFPROBE) as c:
        for i in range(N):
            c.escribir(_frame(i))
        assert not final.exists()                       # aún no existe el nombre final
        assert (final.with_name(final.stem + ".part.mp4")).exists()
    assert final.exists() and not final.with_name(final.stem + ".part.mp4").exists()
    datos = _sonda(final)
    video = next(s for s in datos["streams"] if s["codec_type"] == "video")
    audio_s = [s for s in datos["streams"] if s["codec_type"] == "audio"]
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
    assert video["r_frame_rate"] == "25/1" and (video["width"], video["height"]) == (W, H)
    assert len(audio_s) == 1
    assert abs(float(datos["format"]["duration"]) - 2.0) < 0.1


def test_error_durante_la_escritura_no_deja_final(proyecto_tmp):
    audio = _wav(proyecto_tmp / "cache" / "voz.wav")
    final = proyecto_tmp / "salidas" / "x.mp4"
    with pytest.raises(RuntimeError):
        with Codificador(final, audio, W, H, fps=25, ffmpeg=FFMPEG, ffprobe=FFPROBE) as c:
            c.escribir(_frame(0))
            raise RuntimeError("fallo simulado")
    assert not final.exists()
    assert not list((proyecto_tmp / "salidas").glob("*.part.mp4"))


def test_proceso_ffmpeg_muerto_da_error_accionable(proyecto_tmp):
    audio = _wav(proyecto_tmp / "cache" / "voz.wav")
    final = proyecto_tmp / "salidas" / "y.mp4"
    with pytest.raises(ErrorAccionable):
        with Codificador(final, audio, W, H, fps=25, ffmpeg=FFMPEG, ffprobe=FFPROBE) as c:
            c.escribir(_frame(0))
            c._proceso.kill()
            for i in range(200):
                c.escribir(_frame(i))
    assert not final.exists()


def test_frame_de_tamano_incorrecto(proyecto_tmp):
    audio = _wav(proyecto_tmp / "cache" / "voz.wav")
    final = proyecto_tmp / "salidas" / "z.mp4"
    with pytest.raises(ValueError):
        with Codificador(final, audio, W, H, fps=25, ffmpeg=FFMPEG, ffprobe=FFPROBE) as c:
            c.escribir(b"corto")
    assert not final.exists()


def test_duracion_distinta_al_audio_falla_la_validacion(proyecto_tmp):
    audio = _wav(proyecto_tmp / "cache" / "voz.wav", seg=2.0)
    final = proyecto_tmp / "salidas" / "w.mp4"
    with pytest.raises(ErrorAccionable):
        with Codificador(final, audio, W, H, fps=25, ffmpeg=FFMPEG, ffprobe=FFPROBE,
                         duracion_esperada_s=10.0) as c:
            for i in range(N):
                c.escribir(_frame(i))
    assert not final.exists()
