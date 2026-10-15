"""Prueba de fondo en video: personaje recortado (sin boca) + 9 bocas calibradas sobre un video de fondo en bucle.
Uso: python render_bgvideo.py <json_v3> <nombre_salida> [completo|busto]"""
import json, math, os, re, subprocess, sys, time
from pathlib import Path
import video_prueba2 as v
from PIL import Image

RAIZ = v.RAIZ
SP = Path(__file__).parent
C3 = RAIZ / "Calibrador3"
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
nombre = sys.argv[2]
modo = sys.argv[3] if len(sys.argv) > 3 else "completo"
ref = json.load(open(RAIZ / "Calibrador2" / "calibracion.json", encoding="utf-8"))["formas"]
BOCAS = json.loads(re.search(r"BOCAS=(\{.*?\});", (C3 / "datos.js").read_text(encoding="utf-8"), re.S).group(1))
pj = Image.open(RAIZ / "Escenas" / "personaje_sin_fondo_sin_boca.png").convert("RGBA")      # 2000x1125
W0, H0 = pj.size
ax, ay, k, rg = cfg["ancla"]["x"], cfg["ancla"]["y"], cfg["k"], cfg.get("r", 0)
aj = cfg.get("ajustes", {})
A0 = (ref["A"]["x"], ref["A"]["y"])
OW, OH = v.W, v.H

ventana = (0, 0, W0, H0) if modo == "completo" else (500, 0, 1500, 562.5)       # en coordenadas del personaje (2000x1125)
x0, y0, x1, y1 = ventana
kv = OW / (x1 - x0)

# capas del personaje con cada boca, ya al tamaño de salida
base = pj.resize((OW, OH), Image.LANCZOS, box=tuple(ventana))
capas = {}
cr, sr = math.cos(math.radians(rg)), math.sin(math.radians(rg))
for vis in "ABCDEFGHX":
    b, f = BOCAS[vis], ref[vis]
    a = {"dx": 0, "dy": 0, "k": 1, "r": 0, **aj.get(vis, {})}
    rx, ry = (f["x"] - A0[0]) * k, (f["y"] - A0[1]) * k
    cx, cy = ax + rx * cr - ry * sr + a["dx"], ay + rx * sr + ry * cr + a["dy"]
    s = f["s"] * k * a["k"]
    im = Image.open(C3 / f"boca_{vis}.png").convert("RGBA")
    im = im.resize((max(1, round(b["w"] * s * kv)), max(1, round(b["h"] * s * kv))), Image.LANCZOS)
    rot = f.get("r", 0) + rg + a["r"]
    if rot:
        im = im.rotate(-rot, expand=True, resample=Image.BICUBIC)
    capa = base.copy()
    capa.alpha_composite(im, (round((cx - x0) * kv - im.width / 2), round((cy - y0) * kv - im.height / 2)))
    capas[vis] = capa

# fondo: la unidad de bucle (1920x1080) recortada a la ventana y escalada a la salida
VWID, VHEI = 1920, 1080
fz = VWID / W0                                   # coordenadas del personaje -> coordenadas del video
cw, ch = (x1 - x0) * fz, (y1 - y0) * fz
vf = f"crop={cw:.2f}:{ch:.2f}:{x0 * fz:.2f}:{y0 * fz:.2f},scale={OW}:{OH}:flags=lanczos"
lector = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-i", str(SP / "bg_loop_unit.mp4"),
                           "-vf", vf, "-t", f"{v.DUR:.3f}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
salida, parcial = RAIZ / f"{nombre}.mp4", RAIZ / f"{nombre}.part.mp4"
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
       "-r", str(v.FPS), "-i", "-", "-i", str(v.AUDIO), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
       "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", f"{v.DUR:.3f}", "-movflags", "+faststart", str(parcial)]
escritor = subprocess.Popen(cmd, stdin=subprocess.PIPE)
vis = v.visemas()
n = OW * OH * 3
t = time.perf_counter()
hechos = 0
for x in vis:
    buf = lector.stdout.read(n)
    while len(buf) < n:
        resto = lector.stdout.read(n - len(buf))
        if not resto:
            break
        buf += resto
    if len(buf) < n:
        break
    fr = Image.frombuffer("RGB", (OW, OH), buf, "raw", "RGB", 0, 1)
    capa = capas[x]
    fr.paste(capa, (0, 0), capa)
    escritor.stdin.write(fr.tobytes())
    hechos += 1
escritor.stdin.close(); escritor.wait(); lector.stdout.close(); lector.wait()
os.replace(parcial, salida)
dt = time.perf_counter() - t
print(f"{nombre}: {hechos} frames en {dt:.1f} s ({hechos / dt:.0f} fps) -> {salida.stat().st_size / 1e6:.1f} MB")
