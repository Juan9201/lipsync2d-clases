"""Prueba de video: la escena del escritorio (mesa recortada + iluminación) con voz, lipsync y parpadeo, y medición de tiempos.

    .venv\\Scripts\\python.exe -I prototipos\\iluminacion\\video_escritorio.py <escritorio.webp> <audio.mp3> [segundos=20] [pose]
Escribe salidas/escritorio_<segundos>s.mp4 e imprime cuánto tarda cada parte por frame y la proyección a una clase de 5 minutos."""
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image

import escena_escritorio as esc                                      # lee la escena (argv[1]) y la pose
from src import rutas
from src.animation import calcular_hablando, generar_parpadeos
from src.audio import convertir_para_analisis, info_audio
from src.biblioteca.modelos import cargar_pose
from src.encoder import Codificador
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.personaje import PersonajeLayer
from src.lipsync import analizar, cues_a_frames, suavizar
from src.render import _a_visemas
from src.timeline import LineaDeTiempo, Toma, semilla_de_clase

FPS = 25
W, H = esc.W, esc.H
VENTANA_FINAL = (40, 45, 1200, 675)                                  # encuadre final: un poco más cerrado que la escena entera


def main():
    audio_origen = Path(sys.argv[2])
    segundos = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].replace(".", "").isdigit() else 20.0
    cache = RAIZ / "cache"
    cache.mkdir(exist_ok=True)
    audio = cache / f"escritorio_{int(segundos)}s.mp3"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-t", str(segundos), "-i", str(audio_origen), "-c", "copy", str(audio)], check=True)
    info = info_audio(audio)

    t0 = time.perf_counter()
    wav = cache / "analisis" / "escritorio.wav"
    convertir_para_analisis(audio, wav)
    res = analizar(wav, cache_dir=cache, reconocedor="phonetic")
    wav.unlink(missing_ok=True)
    frames = suavizar(cues_a_frames(res.cues, res.duracion_s, FPS))
    n = len(frames)
    pose = cargar_pose(RAIZ / "personajes" / "profesor" / "poses" / esc.POSE)
    semilla = semilla_de_clase("escritorio", 0)
    lt = LineaDeTiempo(FPS, n, semilla, _a_visemas(frames), [Toma(0, "E1", pose.id, "PL1")], generar_parpadeos(n, FPS, semilla),
                       calcular_hablando(_a_visemas(frames), n))
    lt.validar()

    # --- preparación (una sola vez): capas de la escena, personaje y mapas de luz ---
    escena = Image.open(esc.ESCENA).convert("RGBA").resize((W, H))
    atras, mesa = esc.separar_mesa(escena)
    fondo = esc.pared()
    base = fondo.copy()
    base.alpha_composite(atras)
    pj_fijo = esc.personaje_rgba()
    mult, suma = esc.mapas_de_luz(pj_fijo)
    alfa = np.asarray(pj_fijo)[..., 3] > 0
    ys, xs = np.where(alfa)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1       # solo se ilumina donde hay personaje
    mult_c, suma_c = mult[y0:y1, x0:x1], suma[y0:y1, x0:x1]

    sw, sh = round(W * esc.ESCALA), round(H * esc.ESCALA)
    capa_pj = PersonajeLayer({pose.id: pose}, ventana_plano(pose, "PL1"), (sw, sh))
    e = W / pose.lienzo[0]
    ox = round(esc.CABEZA[0] - pose.anclas.cabeza.x * e * esc.ESCALA)
    oy = round(esc.CABEZA[1] - pose.anclas.cabeza.y * e * esc.ESCALA)
    prep = time.perf_counter() - t0

    final = RAIZ / "salidas" / f"escritorio_{int(segundos)}s.mp4"
    tiempos = {"personaje": 0.0, "luz": 0.0, "composición": 0.0, "encuadre": 0.0, "codificación": 0.0}
    t_bucle = time.perf_counter()
    with Codificador(final, audio, VENTANA_FINAL[2] * 0 + 1280, 720, FPS, duracion_esperada_s=info.duracion_s) as enc:
        for i in range(n):
            ctx = ContextoFrame(i, i / FPS, (sw, sh), lt.toma_en(i), lt.visema_en(i), lt.parpadeando(i), 1.0, 0.0, 0.0, lt.fase_ojos(i))
            t = time.perf_counter()
            pequeno = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))                    # el personaje de este frame (cuerpo, ojos y boca)
            for c in capa_pj.renderizar(ctx):
                xa, ya = max(c.x, 0), max(c.y, 0)
                pequeno.alpha_composite(c.imagen.crop((xa - c.x, ya - c.y, min(c.x + c.imagen.width, sw) - c.x, min(c.y + c.imagen.height, sh) - c.y)), dest=(xa, ya))
            lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            lienzo.alpha_composite(pequeno, dest=(max(ox, 0), max(oy, 0)), source=(max(-ox, 0), max(-oy, 0)))
            tiempos["personaje"] += time.perf_counter() - t
            t = time.perf_counter()
            region = lienzo.crop((x0, y0, x1, y1))
            iluminado = esc.aplicar_luz(region, mult_c, suma_c)
            tiempos["luz"] += time.perf_counter() - t
            t = time.perf_counter()
            cuadro = base.copy()
            cuadro.alpha_composite(iluminado, dest=(x0, y0))
            cuadro.alpha_composite(mesa)
            tiempos["composición"] += time.perf_counter() - t
            t = time.perf_counter()
            vx, vy, vw, vh = VENTANA_FINAL
            salida = cuadro.convert("RGB").resize((1280, 720), Image.LANCZOS, box=(vx, vy, vx + vw, vy + vh))
            tiempos["encuadre"] += time.perf_counter() - t
            t = time.perf_counter()
            enc.escribir(salida.tobytes())
            tiempos["codificación"] += time.perf_counter() - t
    bucle = time.perf_counter() - t_bucle
    print(f"\n{n} frames ({n / FPS:.1f} s de video) · preparación {prep:.1f} s · bucle {bucle:.1f} s ({1000 * bucle / n:.0f} ms/frame)")
    for k, v in tiempos.items():
        print(f"  {k:<13} {1000 * v / n:6.1f} ms/frame  ({100 * v / bucle:4.1f} %)")
    por_clase = (bucle / n) * 7500 + prep
    print(f"proyección de una clase de 5 min: {por_clase:.0f} s ({por_clase / 60:.1f} min) con un trabajador; MP4 {final.stat().st_size / 1e6:.1f} MB en {n / FPS:.0f} s")
    print("listo", final)


if __name__ == "__main__":
    main()
