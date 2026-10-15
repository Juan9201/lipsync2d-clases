"""Prueba de las 11 poses 3/4 calibradas: mosaico de control y un video que recorre todas las poses con la voz y el fondo en video.
Uso: python render_multipose.py"""
import json, os, subprocess, sys, time
from pathlib import Path
SP = Path("C:/Users/JUAN02~1/AppData/Local/Temp/claude/C--Users-Juan-02-Desktop-Fase-1/5b2db2e0-a94e-4afb-b9d9-608060213afd/scratchpad")
sys.path.insert(0, str(SP))
import video_prueba2 as v
from PIL import Image, ImageDraw, ImageOps

RAIZ = v.RAIZ
C4 = RAIZ / "Calibrador4"
TODAS = json.load(open(C4 / os.environ.get("CAL", "calibraciones_34_todas.json"), encoding="utf-8"))["poses"]
ALINEAR = os.environ.get("ALINEAR") in ("1", "2")        # 1 = por el pelo, 2 = por la boca A calibrada
SALIDA_NOMBRE = os.environ.get("SALIDA", "prueba20_todas_las_poses")
import re
_t = (C4 / "datos34.js").read_text(encoding="utf-8")
DCAB = {p["nombre"]: p["dcab"] for p in json.loads(re.search(r"const POSES=(\[.*?\]);", _t, re.S).group(1))}
ORDEN = ["neutro_01", "explicar_01", "pulgar_01", "señalar_01", "bienvenida_01", "bienvenida_02", "bienvenida_03",
         "pregunta_01", "libreta_01", "libreta_02", "libreta_03"]
OW, OH = v.W, v.H
VENT = (1150, 100, 2750, 1000)
x0, y0, x1, y1 = VENT
kv = OW / (x1 - x0)
SPR = {vis: Image.open(C4 / "bocas" / f"boca34_{vis}.png").convert("RGBA") for vis in "ABCDEFGHX"}


def capas_de(nombre):
    cfg = TODAS[nombre]
    pose = Image.open(RAIZ / "Torso Organizado" / "Tres cuartos derecha" / f"tres_cuartos_der_{nombre}.png").convert("RGBA")
    # alineación de la cabeza: la ventana se desplaza lo que la cabeza de esta pose se aparta de la del neutro
    if os.environ.get("ALINEAR") == "2":
        a, a0 = cfg["formas"]["A"], TODAS["neutro_01"]["formas"]["A"]
        dx, dy = a["x"] - a0["x"], a["y"] - a0["y"]            # la boca A de cada pose cae donde la del neutro
    else:
        dx, dy = (DCAB[nombre] if ALINEAR else (0, 0))
    x0, y0, x1, y1 = VENT[0] + dx, VENT[1] + dy, VENT[2] + dx, VENT[3] + dy
    base = pose.resize((OW, OH), Image.LANCZOS, box=(x0, y0, x1, y1))
    out = {}
    for vis in "ABCDEFGHX":
        f = cfg["formas"][vis]
        im = SPR[vis]
        if bool(cfg["espejo"]) != bool(f.get("m")):
            im = ImageOps.mirror(im)
        s = f["s"] * kv
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        if f.get("r"):
            im = im.rotate(-f["r"], expand=True, resample=Image.BICUBIC)
        capa = base.copy()
        capa.alpha_composite(im, (round((f["x"] - x0) * kv - im.width / 2), round((f["y"] - y0) * kv - im.height / 2)))
        out[vis] = capa
    return out


# 1) mosaico de control: una fila por pose, una columna por forma (solo sin alineación de cabezas)
if os.environ.get("SIN_MOSAICO") != "1" and not ALINEAR:
    CW, CH = 200, 150
    mos = Image.new("RGB", (110 + CW * 9, CH * len(ORDEN)), (24, 26, 30)); d = ImageDraw.Draw(mos)
    for i, nombre in enumerate(ORDEN):
        capas = capas_de(nombre)
        a = TODAS[nombre]["formas"]["A"]
        mx, my = int((a["x"] - x0) * kv), int((a["y"] - y0) * kv)
        d.text((6, i * CH + 6), nombre + ("\n(reflejo)" if TODAS[nombre]["espejo"] else ""), fill=(255, 220, 120))
        for j, vis in enumerate("ABCDEFGHX"):
            fr = Image.new("RGB", (OW, OH), (205, 205, 205)); fr.paste(capas[vis], (0, 0), capas[vis])
            mos.paste(fr.crop((mx - CW // 2, my - 60, mx + CW // 2, my + CH - 60)), (110 + j * CW, i * CH))
    for j, vis in enumerate("ABCDEFGHX"):
        d.text((110 + j * CW + 4, 2), vis, fill=(120, 220, 255))
    mos.save(RAIZ / f"_{SALIDA_NOMBRE}_mosaico.png")
    print("mosaico listo", mos.size)
    if os.environ.get("SOLO_MOSAICO") == "1":
        sys.exit(0)

# 2) video que recorre las 11 poses, cortando en pausas (visema X) cercanas a cada punto
vis = v.visemas(); n = len(vis); N = len(ORDEN)
cortes = [0]
for k in range(1, N):
    objetivo = round(k * n / N)
    cand = [i for i in range(max(1, objetivo - 50), min(n, objetivo + 50)) if vis[i] == "X" and vis[i - 1] != "X"]
    cortes.append(min(cand, key=lambda i: abs(i - objetivo)) if cand else objetivo)
cortes.append(n)
print("cortes (s):", [round(c / v.FPS, 1) for c in cortes[:-1]])
fz = 1920 / 3840
vf = f"crop={(x1 - x0) * fz:.2f}:{(y1 - y0) * fz:.2f}:{x0 * fz:.2f}:{y0 * fz:.2f},scale={OW}:{OH}:flags=lanczos"
lector = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-i", str(SP / "bg_loop_unit.mp4"),
                           "-vf", vf, "-t", f"{v.DUR:.3f}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
nombre_salida = SALIDA_NOMBRE
salida, parcial = RAIZ / f"{nombre_salida}.mp4", RAIZ / f"{nombre_salida}.part.mp4"
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(v.FPS),
       "-i", "-", "-i", str(v.AUDIO), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
       "-c:a", "copy", "-t", f"{v.DUR:.3f}", "-movflags", "+faststart", str(parcial)]
escritor = subprocess.Popen(cmd, stdin=subprocess.PIPE)
nb = OW * OH * 3; t = time.perf_counter(); hechos = 0
for seg in range(N):
    capas = capas_de(ORDEN[seg])
    for i in range(cortes[seg], cortes[seg + 1]):
        buf = lector.stdout.read(nb)
        while 0 < len(buf) < nb:
            buf += lector.stdout.read(nb - len(buf))
        if len(buf) < nb:
            break
        fr = Image.frombuffer("RGB", (OW, OH), buf, "raw", "RGB", 0, 1)
        fr.paste(capas[vis[i]], (0, 0), capas[vis[i]])
        escritor.stdin.write(fr.tobytes()); hechos += 1
escritor.stdin.close(); escritor.wait(); lector.stdout.close(); lector.wait()
os.replace(parcial, salida)
dt = time.perf_counter() - t
print(f"{nombre_salida}: {hechos} frames en {dt:.1f} s ({hechos / dt:.0f} fps) -> {salida.stat().st_size / 1e6:.1f} MB")
json.dump({"orden": ORDEN, "cortes_s": [round(c / v.FPS, 2) for c in cortes[:-1]]}, open(RAIZ / f"_{SALIDA_NOMBRE}_cortes.json", "w"), indent=1)
