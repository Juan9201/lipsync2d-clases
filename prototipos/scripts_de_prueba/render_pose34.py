"""Pose 3/4 + bocas 3/4 calibradas (JSON v4 del calibrador 3/4) sobre el fondo en video, con la voz de prueba.
Uso: python render_pose34.py <json_v4> <nombre_salida> [completo|busto]"""
import json, os, subprocess, sys, time
from pathlib import Path
SP = Path("C:/Users/JUAN02~1/AppData/Local/Temp/claude/C--Users-Juan-02-Desktop-Fase-1/5b2db2e0-a94e-4afb-b9d9-608060213afd/scratchpad")
sys.path.insert(0, str(SP))
import video_prueba2 as v
from PIL import Image, ImageOps

RAIZ = v.RAIZ
C4 = RAIZ / "Calibrador4"
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
nombre = sys.argv[2]
modo = sys.argv[3] if len(sys.argv) > 3 else "busto"
pose = Image.open(RAIZ / "Torso Organizado" / "Tres cuartos derecha" / f"tres_cuartos_der_{cfg['pose']}.png").convert("RGBA")   # 3840x2160
W0, H0 = pose.size
OW, OH = v.W, v.H
ventana = (0, 0, W0, H0) if modo == "completo" else (1150, 100, 2750, 1000)
x0, y0, x1, y1 = ventana
kv = OW / (x1 - x0)

base = pose.resize((OW, OH), Image.LANCZOS, box=ventana)
capas = {}
for vis in "ABCDEFGHX":
    f = cfg["formas"][vis]
    im = Image.open(C4 / "bocas" / f"boca34_{vis}.png").convert("RGBA")
    if bool(cfg.get("espejo")) != bool(f.get("m")):        # reflejo de la pose combinado con el de la forma
        im = ImageOps.mirror(im)
    s = f["s"] * kv
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    if f.get("r"):
        im = im.rotate(-f["r"], expand=True, resample=Image.BICUBIC)
    capa = base.copy()
    capa.alpha_composite(im, (round((f["x"] - x0) * kv - im.width / 2), round((f["y"] - y0) * kv - im.height / 2)))
    capas[vis] = capa

fz = 1920 / W0
vf = f"crop={(x1 - x0) * fz:.2f}:{(y1 - y0) * fz:.2f}:{x0 * fz:.2f}:{y0 * fz:.2f},scale={OW}:{OH}:flags=lanczos"
lector = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-i", str(SP / "bg_loop_unit.mp4"),
                           "-vf", vf, "-t", f"{v.DUR:.3f}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
salida, parcial = RAIZ / f"{nombre}.mp4", RAIZ / f"{nombre}.part.mp4"
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(v.FPS),
       "-i", "-", "-i", str(v.AUDIO), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
       "-c:a", "copy", "-t", f"{v.DUR:.3f}", "-movflags", "+faststart", str(parcial)]
escritor = subprocess.Popen(cmd, stdin=subprocess.PIPE)
vis = v.visemas(); n = OW * OH * 3; t = time.perf_counter(); hechos = 0
for x in vis:
    buf = lector.stdout.read(n)
    while 0 < len(buf) < n:
        buf += lector.stdout.read(n - len(buf))
    if len(buf) < n:
        break
    fr = Image.frombuffer("RGB", (OW, OH), buf, "raw", "RGB", 0, 1)
    fr.paste(capas[x], (0, 0), capas[x])
    escritor.stdin.write(fr.tobytes()); hechos += 1
escritor.stdin.close(); escritor.wait(); lector.stdout.close(); lector.wait()
os.replace(parcial, salida)
dt = time.perf_counter() - t
print(f"{nombre}: {hechos} frames en {dt:.1f} s ({hechos / dt:.0f} fps) -> {salida.stat().st_size / 1e6:.1f} MB")
hoja = Image.new("RGB", (520 * 3, 300 * 3))
mx = int((cfg["formas"]["A"]["x"] - x0) * kv); my = int((cfg["formas"]["A"]["y"] - y0) * kv)
for i, x in enumerate("ABCDEFGHX"):
    fr = Image.new("RGB", (OW, OH), (200, 200, 200)); fr.paste(capas[x], (0, 0), capas[x])
    hoja.paste(fr.crop((mx - 260, my - 120, mx + 260, my + 180)), ((i % 3) * 520, (i // 3) * 300))
hoja.save(RAIZ / f"_{nombre}_control.png")
