"""Copia los parpadeos con el nombre de su pose (sin tocar los originales) y prueba el pegado de la zona de ojos en las 11 poses 3/4."""
import shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

R = Path(r"C:\Users\Juan 02\Desktop\Fase 1\Temp Real Assest Testing\Torso Organizado")
BL = sorted((R / "Tres cuartos derecha Blink").glob("*.png"))
D = np.load(R / "_blink34_difs.npy")
POSES = sorted((R / "Tres cuartos derecha").glob("tres_cuartos_der_*.png"))
secuencia = [p.name for p in sorted(POSES, key=lambda p: p.name)]
# el orden de las columnas de D es el del catálogo; se reconstruye con el mismo criterio que emparejar_blink34.py
import csv
filas = list(csv.DictReader(open(R / "catalogo.csv", encoding="utf-8-sig")))
cat = [f["archivo_nuevo"] for f in filas if f["vista"] == "Tres cuartos derecha"]
asig = {b.name: cat[int(D[i].argmin())] for i, b in enumerate(BL)}
assert len(set(asig.values())) == 11, "el emparejamiento no es uno a uno"

salida = R / "Tres cuartos derecha Blink Organizado"
salida.mkdir(exist_ok=True)
for b in BL:
    destino = salida / asig[b.name].replace(".png", "_parpadeo.png")
    shutil.copy2(b, destino)
# parpadeos frontales (comparten cabeza con las 32 poses frontales)
fb = R / "Frontal Blink"
shutil.copy2(fb / "Frontal_Blink.png", salida / "frontal_parpadeo.png")
shutil.copy2(fb / "Frontal_Blink_Middle.png", salida / "frontal_parpadeo_medio.png")
print("copiados:", sorted(p.name for p in salida.iterdir()))

# prueba de pegado por pose: zona de ojos = donde cambia la imagen entre pose y parpadeo, dentro de la banda de la cabeza
filas_v = []
for b in BL:
    pose_n = asig[b.name]
    base = Image.open(R / "Tres cuartos derecha" / pose_n).convert("RGBA")
    bl = Image.open(b).convert("RGBA")
    a, c = np.asarray(base).astype(int), np.asarray(bl).astype(int)
    dif = np.abs(a[:, :, :3] - c[:, :, :3]).max(2) > 40
    dif[:300, :] = False; dif[560:, :] = False; dif[:, :1500] = False; dif[:, 2400:] = False
    ys, xs = np.where(dif)
    if len(xs) < 500:
        print(pose_n, "sin diferencias en la zona de ojos"); continue
    x0, x1 = int(np.percentile(xs, 1)), int(np.percentile(xs, 99)); y0, y1 = int(np.percentile(ys, 1)), int(np.percentile(ys, 99))
    M = 16
    caja = (x0 - M, y0 - M, x1 + M, y1 + M)
    m = Image.new("L", base.size, 0); ImageDraw.Draw(m).rounded_rectangle(caja, radius=20, fill=255); m = m.filter(ImageFilter.GaussianBlur(6))
    out = base.copy(); out.paste(bl, (0, 0), m)
    filas_v.append((pose_n.replace("tres_cuartos_der_", "").replace(".png", ""), base, out, caja))
    print(f"{pose_n:36s} zona de ojos x[{x0},{x1}] y[{y0},{y1}]")

W, H = 440, 300
hoja = Image.new("RGB", (110 + W * 2, H * len(filas_v)), (24, 26, 30)); d = ImageDraw.Draw(hoja)
for i, (n, base, out, caja) in enumerate(filas_v):
    cx, cy = (caja[0] + caja[2]) // 2, (caja[1] + caja[3]) // 2
    d.text((4, i * H + 6), n, fill=(255, 220, 120))
    for j, im in enumerate((base, out)):
        f = Image.new("RGBA", im.size, (228, 228, 228, 255)); f.alpha_composite(im)
        hoja.paste(f.crop((cx - 330, cy - 110, cx + 330, cy + 190)).convert("RGB").resize((W, int(300 * W / 660))), (110 + j * W, i * H))
hoja.save(R.parent / "_blink34_integracion.png")
print("mosaico", hoja.size)
