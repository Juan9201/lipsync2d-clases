"""Renderiza el juego de bocas calibrado sobre una escena usando el JSON v3 del calibrador de escena.
Uso: python render_escena3.py <json> [nombre_salida]"""
import json, math, os, re, subprocess, sys, time
from pathlib import Path
import video_prueba2 as v
from PIL import Image

RAIZ = v.RAIZ
C3 = RAIZ / "Calibrador3"
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
salida_nombre = sys.argv[2] if len(sys.argv) > 2 else "prueba_escena"
ref = json.load(open(RAIZ / "Calibrador2" / "calibracion.json", encoding="utf-8"))["formas"]
BOCAS = json.loads(re.search(r"BOCAS=(\{.*?\});", (C3 / "datos.js").read_text(encoding="utf-8"), re.S).group(1))
escena = Image.open(C3 / cfg["imagen"]).convert("RGB")
W0, H0 = escena.size
ax, ay, k, rg = cfg["ancla"]["x"], cfg["ancla"]["y"], cfg["k"], cfg.get("r", 0)
aj = cfg.get("ajustes", {})
A0 = (ref["A"]["x"], ref["A"]["y"])


def frames(ventana):
    x0, y0, x1, y1 = ventana
    kv = v.W / (x1 - x0)
    vista = escena.resize((v.W, v.H), Image.LANCZOS, box=tuple(ventana)).convert("RGBA")
    out = {}
    cr, sr = math.cos(math.radians(rg)), math.sin(math.radians(rg))
    for vis in "ABCDEFGHX":
        b, f = BOCAS[vis], ref[vis]
        a = {"dx": 0, "dy": 0, "k": 1, "r": 0, **aj.get(vis, {})}
        rx, ry = (f["x"] - A0[0]) * k, (f["y"] - A0[1]) * k
        cx = ax + rx * cr - ry * sr + a["dx"]
        cy = ay + rx * sr + ry * cr + a["dy"]
        s = f["s"] * k * a["k"]
        im = Image.open(C3 / f"boca_{vis}.png").convert("RGBA")
        im = im.resize((max(1, round(b["w"] * s * kv)), max(1, round(b["h"] * s * kv))), Image.LANCZOS)
        rot = (f.get("r", 0) + rg + a["r"])
        if rot:
            im = im.rotate(-rot, expand=True, resample=Image.BICUBIC)
        fr = vista.copy()
        fr.alpha_composite(im, (round((cx - x0) * kv - im.width / 2), round((cy - y0) * kv - im.height / 2)))
        out[vis] = fr.convert("RGB").tobytes()
    return out


def video(nombre, ventana):
    cuadros = frames(ventana)
    vis = v.visemas()
    salida, parcial = RAIZ / f"{nombre}.mp4", RAIZ / f"{nombre}.part.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{v.W}x{v.H}",
           "-r", str(v.FPS), "-i", "-", "-i", str(v.AUDIO), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", f"{v.DUR:.3f}", "-movflags", "+faststart", str(parcial)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for x in vis:
        p.stdin.write(cuadros[x])
    p.stdin.close(); p.wait()
    os.replace(parcial, salida)
    return cuadros


def ventana(ancho, ax_rel=0.53, ay_rel=0.48):
    alto = ancho * 9 / 16
    x0 = min(max(ax - ax_rel * ancho, 0), max(W0 - ancho, 0))
    y0 = min(max(ay - ay_rel * alto, 0), max(H0 - alto, 0))
    return (x0, y0, x0 + min(ancho, W0), y0 + min(ancho, W0) * 9 / 16)


# completo (recorte 16:9 de toda la imagen) y busto (ventana de 1600*k px de ancho)
alto_full = min(H0, W0 * 9 / 16)
completo = (0, 0, alto_full * 16 / 9, alto_full)
t = time.perf_counter()
video(f"{salida_nombre}_completo", completo)
busto = ventana(1600 * k)
c = video(f"{salida_nombre}_busto", busto)
print(f"listo en {time.perf_counter() - t:.1f} s")
kv = v.W / (busto[2] - busto[0])
mx, my = int((ax - busto[0]) * kv), int((ay - busto[1]) * kv)
hoja = Image.new("RGB", (520 * 3, 300 * 3))
for i, x in enumerate("ABCDEFGHX"):
    im = Image.frombytes("RGB", (v.W, v.H), c[x]).crop((mx - 260, my - 110, mx + 260, my + 190))
    hoja.paste(im, ((i % 3) * 520, (i // 3) * 300))
hoja.save(RAIZ / f"_{salida_nombre}_control.png")
