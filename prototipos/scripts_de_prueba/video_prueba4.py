"""Prueba 4: igual que la 3, pero la línea de cierre en el punto marcado por el usuario y el borde superior de la boca fijo."""
import os, subprocess, time
import numpy as np
import video_prueba2 as v
from PIL import Image

RAIZ = v.RAIZ
ESC = float(os.environ.get("ESC", "0.16"))
LINEA_4K = (3087, 583)            # centro de la línea verde del usuario, en la escena 4K


def tope(im):
    a = np.asarray(im)[:, :, 3]
    return int(np.where((a > 20).any(1))[0][0])


def preparar(ventana):
    x0, y0, x1, y1 = ventana
    vista = v.escena.resize((v.W, v.H), Image.LANCZOS, box=ventana).convert("RGBA")
    k = v.W / (x1 - x0)
    s = ESC * k
    cx, cy = (LINEA_4K[0] - x0) * k, (LINEA_4K[1] - y0) * k
    base = {x: Image.open(RAIZ / os.environ.get("SPR", "Cartoon") / f"P1_boca_{x}.png").convert("RGBA") for x in "ABCDEFGHX"}
    tope_A = tope(base["A"])                                   # borde superior de la boca cerrada (línea)
    y_tope = cy + (tope_A - base["A"].height / 2) * s          # el borde superior queda fijo para todas
    cuadros = {}
    for vis, im0 in base.items():
        t = tope(im0)
        im = im0.resize((max(1, round(im0.width * s)), max(1, round(im0.height * s))), Image.LANCZOS)
        fr = vista.copy()
        fr.alpha_composite(im, (round(cx - im.width / 2), round(y_tope - t * s)))
        cuadros[vis] = fr.convert("RGB").tobytes()
    return cuadros


if __name__ == "__main__":
    ventana = (2240, 150, 3840, 1050)
    cuadros = preparar(ventana)
    vis = v.visemas()
    salida, parcial = RAIZ / "prueba12_hoja4.mp4", RAIZ / "prueba12_hoja4.part.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{v.W}x{v.H}", "-r", str(v.FPS), "-i", "-", "-i", str(v.AUDIO), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy",
           "-t", f"{v.DUR:.3f}", "-movflags", "+faststart", str(parcial)]
    t = time.perf_counter()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for x in vis:
        p.stdin.write(cuadros[x])
    p.stdin.close(); p.wait()
    os.replace(parcial, salida)
    print(f"{time.perf_counter() - t:.1f} s -> {salida}")
    hoja = Image.new("RGB", (520 * 4, 300 * 2))
    for k, x in enumerate("ABCDEFGH"):
        im = Image.frombytes("RGB", (v.W, v.H), cuadros[x]).crop((440, 90, 960, 390))
        hoja.paste(im, ((k % 4) * 520, (k // 4) * 300))
    hoja.save(RAIZ / "_prueba12_control.png")
