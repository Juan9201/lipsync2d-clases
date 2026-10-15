"""FR-033: interrumpir un render a mitad no deja un MP4 corrupto con el nombre final."""
import subprocess
import sys
import time

import pytest

from pruebas.utiles import EJEMPLO, FFMPEG, RAIZ, recortar_audio
from src.render import ParametrosRender, renderizar

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and EJEMPLO.exists()), reason="faltan ffmpeg o el audio de ejemplo")]


def test_matar_el_render_a_mitad_no_deja_mp4_final(proyecto_con_assets):
    p = proyecto_con_assets
    audio = recortar_audio(EJEMPLO, p / "clases" / "larga.mp3", 90, inicio=0)
    codigo = ("from pathlib import Path; from src.render import ParametrosRender, renderizar; "
              f"renderizar(ParametrosRender(personaje='profe', audio=Path(r'{audio}')), raiz=Path(r'{p}'))")
    proc = subprocess.Popen([sys.executable, "-c", codigo], cwd=RAIZ)
    try:
        parcial = None
        for _ in range(300):                        # hasta 30 s esperando a que empiece a escribir
            parciales = list((p / "salidas").glob("*.part.mp4"))
            if parciales and parciales[0].stat().st_size > 0:
                parcial = parciales[0]
                break
            time.sleep(0.1)
        assert parcial is not None, "el render no llegó a escribir el archivo parcial"
        proc.kill()                                 # corte brusco, como un apagón
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    assert not list((p / "salidas").glob("larga_*.mp4")) or all(
        f.name.endswith(".part.mp4") for f in (p / "salidas").glob("larga_*.mp4"))
    finales = [f for f in (p / "salidas").glob("*.mp4") if not f.name.endswith(".part.mp4")]
    assert finales == []


def test_tras_un_corte_se_puede_relanzar_y_limpia_el_parcial(proyecto_con_assets):
    p = proyecto_con_assets
    audio = recortar_audio(EJEMPLO, p / "clases" / "corta.mp3", 5, inicio=0)
    (p / "salidas").mkdir(exist_ok=True)
    huerfano = p / "salidas" / f"corta_{__import__('datetime').date.today():%Y%m%d}.part.mp4"
    huerfano.write_bytes(b"basura de un render interrumpido")
    final = renderizar(ParametrosRender(personaje="profe", audio=audio), raiz=p)
    assert final.exists() and not huerfano.exists()
