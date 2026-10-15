"""NFR-003: el desfase entre audio y visemas es <= 1 frame (40 ms)."""
import json
import subprocess

import numpy as np
import pytest

from pruebas.utiles import EJEMPLO, FFMPEG, FFPROBE, recortar_audio
from src.audio import convertir_para_analisis
from src.lipsync import analizar, cues_a_frames, suavizar
from src.render import ParametrosRender, renderizar

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and EJEMPLO.exists()), reason="faltan ffmpeg o el audio de ejemplo")]
FPS = 25


def test_los_cambios_de_visema_caen_a_menos_de_un_frame_de_su_instante_real(proyecto_con_assets):
    """Compara cada frontera de visema renderizada con la frontera original de Rhubarb."""
    p = proyecto_con_assets
    audio = recortar_audio(EJEMPLO, p / "clases" / "a.mp3", 40, inicio=20)
    res = analizar(convertir_para_analisis(audio, p / "cache" / "a.wav"), cache_dir=p / "cache")
    frames = suavizar(cues_a_frames(res.cues, res.duracion_s, FPS))
    fronteras_frames = [i / FPS for i in range(1, len(frames)) if frames[i] != frames[i - 1]]
    fronteras_reales = np.array(sorted({c.inicio for c in res.cues} | {c.fin for c in res.cues}))
    errores_ms = np.array([np.min(np.abs(fronteras_reales - t)) for t in fronteras_frames]) * 1000
    assert len(errores_ms) > 50
    assert np.percentile(errores_ms, 95) <= 40, f"p95 = {np.percentile(errores_ms, 95):.0f} ms"
    assert abs(np.mean([t - fronteras_reales[np.argmin(np.abs(fronteras_reales - t))] for t in fronteras_frames])) * 1000 <= 20


def test_el_audio_y_el_video_del_mp4_arrancan_juntos(proyecto_con_assets):
    p = proyecto_con_assets
    audio = recortar_audio(EJEMPLO, p / "clases" / "b.mp3", 10, inicio=20)
    final = renderizar(ParametrosRender(personaje="profe", audio=audio), raiz=p)
    out = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_streams", str(final)],
                         capture_output=True, text=True, check=True).stdout
    inicio = {s["codec_type"]: float(s.get("start_time", 0)) for s in json.loads(out)["streams"]}
    assert abs(inicio["video"] - inicio["audio"]) <= 0.040, inicio
