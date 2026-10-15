"""Prueba: pegar solo la zona de los ojos de las imágenes de parpadeo sobre poses frontales abiertas."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

R = Path(r"C:\Users\Juan 02\Desktop\Fase 1\Temp Real Assest Testing")
FR = R / "Torso Organizado" / "Frontal"
cerr = Image.open(R / "Torso Organizado" / "Frontal Blink" / "Frontal_Blink.png").convert("RGBA")
medio = Image.open(R / "Torso Organizado" / "Frontal Blink" / "Frontal_Blink_Middle.png").convert("RGBA")

# zona de los ojos = donde difieren la imagen cerrada y la intermedia (misma cabeza, solo cambian los ojos), en la franja de la cara
a, b = np.asarray(cerr).astype(int), np.asarray(medio).astype(int)
dif = np.abs(a[:, :, :3] - b[:, :, :3]).max(2) > 35
dif[:352, :] = False; dif[480:, :] = False          # solo la banda de los lentes: sin cejas ni mejillas
# un recuadro por ojo (se parte la franja por el puente de la nariz), para no tocar nada entre los ojos ni a los lados
ys, xs = np.where(dif)
corte = 1930
mascara = Image.new("L", cerr.size, 0); dm = ImageDraw.Draw(mascara)
for nombre, sel in (("izq", xs < corte), ("der", xs >= corte)):
    x0, x1 = int(np.percentile(xs[sel], 2)), int(np.percentile(xs[sel], 98)); y0, y1 = int(np.percentile(ys[sel], 2)), int(np.percentile(ys[sel], 98))
    M = 14
    print("ojo", nombre, "x", x0, x1, "y", y0, y1)
    dm.rounded_rectangle((x0 - M, y0 - M, x1 + M, y1 + M), radius=18, fill=255)
mascara = mascara.filter(ImageFilter.GaussianBlur(5))
caja = (1650, 355, 2230, 480)


def con_ojos(abierta_png, fuente):
    base = Image.open(abierta_png).convert("RGBA")
    out = base.copy(); out.paste(fuente, (0, 0), mascara)
    return base, out


filas = []
for nombre in ["frontal_neutro_01", "frontal_explicar_01", "frontal_pulgar_01", "frontal_libreta_01"]:
    base, c = con_ojos(FR / f"{nombre}.png", cerr)
    _, m = con_ojos(FR / f"{nombre}.png", medio)
    filas.append((nombre, base, m, c))
crop = (caja[0] - 60, caja[1] - 90, caja[2] + 60, caja[3] + 70)
w, h = crop[2] - crop[0], crop[3] - crop[1]
esc = 520 / w
hoja = Image.new("RGB", (3 * 520 + 120, len(filas) * int(h * esc) + 30), (24, 26, 30)); d = ImageDraw.Draw(hoja)
for j, et in enumerate(["abierta (original)", "con parpadeo a medias", "con parpadeo cerrado"]):
    d.text((120 + j * 520 + 6, 8), et, fill=(120, 220, 255))
for i, (n, *tri) in enumerate(filas):
    d.text((4, 40 + i * int(h * esc)), n.replace("frontal_", ""), fill=(255, 220, 120))
    for j, im in enumerate(tri):
        f = Image.new("RGBA", im.size, (228, 228, 228, 255)); f.alpha_composite(im)
        hoja.paste(f.crop(crop).convert("RGB").resize((520, int(h * esc))), (120 + j * 520, 30 + i * int(h * esc)))
hoja.save(R / "_blink_integracion.png"); print("hoja", hoja.size)
