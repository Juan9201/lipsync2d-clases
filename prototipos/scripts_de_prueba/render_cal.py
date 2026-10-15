"""Renderiza el video de prueba aplicando los valores exportados por calibrador.html (calibracion.json)."""
import json, os, subprocess, sys, time
from pathlib import Path
import video_prueba2 as v
from PIL import Image

RAIZ = v.RAIZ
CAL = RAIZ / os.environ.get("CAL", "Calibrador")
cfg = json.load(open(CAL / "calibracion.json", encoding="utf-8"))
datos = {}
import re
txt = (CAL / "datos.js").read_text(encoding="utf-8")
BOCAS = json.loads(re.search(r"BOCAS=(\{.*?\});", txt, re.S).group(1))
VENT = json.loads(re.search(r"VENTANA=(\[.*?\]);", txt).group(1))
LIENZO = (1200, 900)

x0, y0, x1, y1 = VENT
k = v.W / (x1 - x0)                       # ventana 4K -> vista 1280x720
vista = v.escena.resize((v.W, v.H), Image.LANCZOS, box=tuple(VENT)).convert("RGBA")
cuadros = {}
for vis in "ABCDEFGHX":
    b, f = BOCAS[vis], cfg["formas"][vis]     # v2: centro (x, y) en la escena 4K y escala, propios de cada forma
    im = Image.open(CAL / f"boca_{vis}.png").convert("RGBA")
    ancho, alto = b["w"] * f["s"], b["h"] * f["s"]
    im = im.resize((max(1, round(ancho * k)), max(1, round(alto * k))), Image.LANCZOS)
    if f.get("r"):                                       # rotación en grados, positiva = sentido horario
        im = im.rotate(-f["r"], expand=True, resample=Image.BICUBIC)
    fr = vista.copy()
    fr.alpha_composite(im, (round((f["x"] - x0) * k - im.width / 2), round((f["y"] - y0) * k - im.height / 2)))
    cuadros[vis] = fr.convert("RGB").tobytes()

vis = v.visemas()
salida, parcial = RAIZ / (os.environ.get("OUT", "prueba_calibrada") + ".mp4"), RAIZ / (os.environ.get("OUT", "prueba_calibrada") + ".part.mp4")
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{v.W}x{v.H}",
       "-r", str(v.FPS), "-i", "-", "-i", str(v.AUDIO), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
       "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", f"{v.DUR:.3f}", "-movflags", "+faststart", str(parcial)]
t = time.perf_counter()
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for x in vis:
    p.stdin.write(cuadros[x])
p.stdin.close(); p.wait()
os.replace(parcial, salida)
print(f"{time.perf_counter() - t:.1f} s -> {salida}")
hoja = Image.new("RGB", (520 * 4, 300 * 3))
for i, x in enumerate("ABCDEFGHX"):
    im = Image.frombytes("RGB", (v.W, v.H), cuadros[x]).crop((440, 90, 960, 390))
    hoja.paste(im, ((i % 4) * 520, (i // 4) * 300))
hoja.save(RAIZ / (os.environ.get("OUT", "prueba_calibrada") + "_control.png"))
