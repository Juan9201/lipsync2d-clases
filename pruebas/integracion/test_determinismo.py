"""NFR-004, FR-107: misma entrada y misma semilla producen frames idénticos."""
import shutil
import subprocess

import pytest

from pruebas.utiles import EJEMPLO, FFMPEG, recortar_audio
from src.render import ParametrosRender, renderizar

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and EJEMPLO.exists()), reason="faltan ffmpeg o el audio de ejemplo")]


def _huella_de_frames(video) -> list:
    """Suma MD5 de cada frame decodificado (ignora el audio y los metadatos del contenedor)."""
    out = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(video), "-an", "-f", "framemd5", "-"],
                         capture_output=True, text=True, check=True).stdout
    return [l.split(",")[-1].strip() for l in out.splitlines() if l and not l.startswith("#")]


def test_dos_renders_con_la_misma_semilla_dan_los_mismos_frames(proyecto_con_assets):
    p = proyecto_con_assets
    audio = recortar_audio(EJEMPLO, p / "clases" / "clase.mp3", 8, inicio=10)
    primero = renderizar(ParametrosRender(personaje="profe", audio=audio, semilla=7), raiz=p)
    copia = p / "cache" / "primero.mp4"
    shutil.copyfile(primero, copia)
    primero.unlink()
    segundo = renderizar(ParametrosRender(personaje="profe", audio=audio, semilla=7), raiz=p)
    h1, h2 = _huella_de_frames(copia), _huella_de_frames(segundo)
    assert len(h1) == len(h2) > 100 and h1 == h2
