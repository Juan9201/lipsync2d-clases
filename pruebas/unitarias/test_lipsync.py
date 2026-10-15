"""FR-020, FR-021, FR-022: parseo de Rhubarb, suavizado, caché y binario ausente."""
import json
from pathlib import Path

import numpy as np
import pytest

from src.errores import EntornoIncompleto
from src.lipsync import (Cue, analizar, cues_a_frames, parsear_salida_rhubarb, suavizar)

RAIZ = Path(__file__).resolve().parents[2]
RHUBARB = RAIZ / "herramientas" / "rhubarb" / "rhubarb.exe"
FPS = 25


def _runs(frames):
    runs, ini = [], 0
    for i in range(1, len(frames) + 1):
        if i == len(frames) or frames[i] != frames[ini]:
            runs.append((frames[ini], i - ini)); ini = i
    return runs


def test_parseo_de_la_salida_json():
    datos = {"metadata": {"duration": 1.0},
             "mouthCues": [{"start": 0.0, "end": 0.4, "value": "X"}, {"start": 0.4, "end": 1.0, "value": "B"}]}
    cues, dur = parsear_salida_rhubarb(json.dumps(datos))
    assert dur == 1.0 and cues == [Cue(0.0, 0.4, "X"), Cue(0.4, 1.0, "B")]


def test_cues_a_frames_cubre_toda_la_duracion():
    cues = [Cue(0.0, 0.4, "X"), Cue(0.4, 1.0, "B")]
    frames = cues_a_frames(cues, 1.0, FPS)
    assert len(frames) == 25 and frames[0] == "X" and frames[-1] == "B"


def test_cierre_A_corto_no_se_pierde_al_muestrear():
    cues = [Cue(0.0, 0.5, "B"), Cue(0.5, 0.53, "A"), Cue(0.53, 1.0, "C")]   # A de 30 ms < 1 frame
    frames = cues_a_frames(cues, 1.0, FPS)
    assert "A" in frames


def test_suavizado_sin_visemas_cortos_salvo_A():
    rng = np.random.default_rng(3)
    frames = list(rng.choice(list("ABCDEFGHX"), size=500))
    out = suavizar(frames, min_frames=2)
    assert len(out) == len(frames)
    for valor, largo in _runs(out):
        assert largo >= 2 or valor == "A"


def test_suavizado_conserva_las_A_aisladas():
    frames = list("BBBBB") + ["A"] + list("CCCCC")
    assert "A" in suavizar(frames, min_frames=2)


def test_suavizado_absorbe_un_frame_suelto():
    out = suavizar(list("BBBB") + ["D"] + list("BBBB"), min_frames=2)
    assert out == list("BBBBBBBBB")


def test_suavizado_en_los_bordes():
    assert suavizar(["D"] + list("BBBB"), min_frames=2) == list("BBBBB")
    assert suavizar(list("BBBB") + ["D"], min_frames=2) == list("BBBBB")


def test_binario_ausente_da_error_accionable(proyecto_tmp):
    wav = proyecto_tmp / "cache" / "a.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(EntornoIncompleto) as exc:
        analizar(wav, rhubarb=proyecto_tmp / "no" / "rhubarb.exe", cache_dir=proyecto_tmp / "cache")
    assert "instalar.ps1" in str(exc.value)


@pytest.mark.integracion
@pytest.mark.skipif(not RHUBARB.exists(), reason="Rhubarb no instalado")
def test_analisis_real_y_cache(proyecto_tmp):
    import subprocess
    ffmpeg = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
    ejemplo = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"
    if not (ffmpeg.exists() and ejemplo.exists()):
        pytest.skip("faltan ffmpeg o el audio de ejemplo")
    wav = proyecto_tmp / "cache" / "ñ ejemplo.wav"
    subprocess.run([str(ffmpeg), "-v", "error", "-y", "-t", "15", "-i", str(ejemplo),
                    "-ar", "16000", "-ac", "1", str(wav)], check=True)
    r1 = analizar(wav, rhubarb=RHUBARB, cache_dir=proyecto_tmp / "cache")
    assert not r1.desde_cache and r1.duracion_s > 14
    r2 = analizar(wav, rhubarb=RHUBARB, cache_dir=proyecto_tmp / "cache")
    assert r2.desde_cache and r2.cues == r1.cues
