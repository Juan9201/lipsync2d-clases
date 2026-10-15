"""FR-011, FR-031: render de 10 s con bocas placeholder; ffprobe valida el resultado."""
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from src.biblioteca.placeholders import crear_pose_placeholder
from src.render import ParametrosRender, renderizar

RAIZ = Path(__file__).resolve().parents[2]
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffprobe.exe"
RHUBARB = RAIZ / "herramientas" / "rhubarb" / "rhubarb.exe"
EJEMPLO = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and RHUBARB.exists() and EJEMPLO.exists()),
                                 reason="faltan ffmpeg, Rhubarb o el audio de ejemplo")]


def _sonda(ruta):
    out = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(ruta)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture
def proyecto(proyecto_tmp):
    crear_pose_placeholder(proyecto_tmp / "personajes" / "profe" / "poses" / "P1_demo", "P1", lienzo=(1280, 720))
    fondo = proyecto_tmp / "escenarios" / "E1_aula" / "fondo.png"
    fondo.parent.mkdir(parents=True)
    Image.new("RGB", (1280, 720), (90, 140, 200)).save(fondo)
    audio = proyecto_tmp / "clases" / "clase ñandú 01.mp3"
    subprocess.run([str(FFMPEG), "-v", "error", "-y", "-t", "10", "-i", str(EJEMPLO), "-c", "copy", str(audio)],
                   check=True)
    return proyecto_tmp, audio


def test_render_de_10_segundos(proyecto):
    raiz, audio = proyecto
    final = renderizar(ParametrosRender(personaje="profe", audio=audio, semilla=3), raiz=raiz)
    assert final.exists() and final.parent == raiz / "salidas" and final.suffix == ".mp4"
    assert not list((raiz / "salidas").glob("*.part.mp4"))
    datos = _sonda(final)
    video = next(s for s in datos["streams"] if s["codec_type"] == "video")
    audios = [s for s in datos["streams"] if s["codec_type"] == "audio"]
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
    assert video["r_frame_rate"] == "25/1" and (video["width"], video["height"]) == (1280, 720)
    assert len(audios) == 1 and audios[0]["codec_name"] == "mp3"        # MP3 copiado sin recodificar
    assert abs(float(datos["format"]["duration"]) - 10.0) < 0.15
    assert not any((raiz / "cache").glob("**/*.wav")), "el WAV temporal de análisis debe borrarse"


def test_sin_guion_funciona_y_avisa(proyecto, caplog):
    raiz, audio = proyecto
    import logging
    with caplog.at_level(logging.INFO):
        final = renderizar(ParametrosRender(personaje="profe", audio=audio), raiz=raiz)
    assert final.exists()
    assert any("sin guion" in r.getMessage().lower() for r in caplog.records)


def test_pose_sin_escenario_ni_respaldo_pide_escenario(proyecto_tmp):
    from src.errores import ErrorAccionable
    crear_pose_placeholder(proyecto_tmp / "personajes" / "profe" / "poses" / "P1_demo", "P1", lienzo=(1280, 720))
    audio = proyecto_tmp / "clases" / "a.mp3"
    subprocess.run([str(FFMPEG), "-v", "error", "-y", "-t", "2", "-i", str(EJEMPLO), "-c", "copy", str(audio)],
                   check=True)
    with pytest.raises(ErrorAccionable) as exc:
        renderizar(ParametrosRender(personaje="profe", audio=audio), raiz=proyecto_tmp)
    assert "escenario" in str(exc.value).lower()
