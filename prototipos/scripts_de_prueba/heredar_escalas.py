"""Hereda del neutro las escalas por forma en las poses donde quedaron en el valor por defecto (0.23). Conserva TODAS tus posiciones y giros.
Genera calibraciones_34_todas_v2.json y un mosaico comparativo, sin tocar tu archivo original."""
import copy, json, sys
from pathlib import Path
SP = Path("C:/Users/JUAN02~1/AppData/Local/Temp/claude/C--Users-Juan-02-Desktop-Fase-1/5b2db2e0-a94e-4afb-b9d9-608060213afd/scratchpad")
sys.path.insert(0, str(SP))
import video_prueba2 as v
from PIL import Image, ImageDraw, ImageOps

RAIZ = v.RAIZ
C4 = RAIZ / "Calibrador4"
orig = json.load(open(C4 / "calibraciones_34_todas.json", encoding="utf-8"))
nuevo = copy.deepcopy(orig)
neutro = orig["poses"]["neutro_01"]["formas"]
cambios = []
for nombre, pose in nuevo["poses"].items():
    if nombre == "neutro_01":
        continue
    for vis, f in pose["formas"].items():
        if abs(f["s"] - 0.23) < 1e-6 and abs(neutro[vis]["s"] - 0.23) > 1e-6:
            cambios.append((nombre, vis, f["s"], neutro[vis]["s"]))
            f["s"] = neutro[vis]["s"]              # mismo centro, nueva escala: la posición que calibraste no se mueve
nuevo["nota"] += " v2: escalas por forma heredadas del neutro donde seguían en 0.23 (solo escala; posiciones y giros intactos)."
json.dump(nuevo, open(C4 / "calibraciones_34_todas_v2.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("formas cambiadas:", len(cambios), "en", len({c[0] for c in cambios}), "poses;", sorted({(c[1], c[3]) for c in cambios}))

OW, OH = v.W, v.H
VENT = (1150, 100, 2750, 1000)
x0, y0, x1, y1 = VENT
kv = OW / (x1 - x0)
SPR = {vis: Image.open(C4 / "bocas" / f"boca34_{vis}.png").convert("RGBA") for vis in "ABCDEFGHX"}


def capa(nombre, cfg_poses, vis):
    cfg = cfg_poses[nombre]
    pose = Image.open(RAIZ / "Torso Organizado" / "Tres cuartos derecha" / f"tres_cuartos_der_{nombre}.png").convert("RGBA")
    base = pose.resize((OW, OH), Image.LANCZOS, box=VENT)
    f = cfg["formas"][vis]
    im = SPR[vis]
    if bool(cfg["espejo"]) != bool(f.get("m")):
        im = ImageOps.mirror(im)
    s = f["s"] * kv
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    if f.get("r"):
        im = im.rotate(-f["r"], expand=True, resample=Image.BICUBIC)
    base.alpha_composite(im, (round((f["x"] - x0) * kv - im.width / 2), round((f["y"] - y0) * kv - im.height / 2)))
    return base, f


# comparación de la forma F (la más desigual) antes y después, en las 11 poses
ORDEN = list(orig["poses"].keys())
CW, CH = 220, 170
mos = Image.new("RGB", (120 + CW * 2, CH * len(ORDEN)), (24, 26, 30)); d = ImageDraw.Draw(mos)
d.text((125, 2), "ANTES (F)", fill=(255, 140, 140)); d.text((125 + CW, 2), "DESPUÉS (F)", fill=(140, 255, 160))
for i, nombre in enumerate(ORDEN):
    d.text((6, i * CH + 6), nombre, fill=(255, 220, 120))
    for j, cfgp in enumerate((orig["poses"], nuevo["poses"])):
        im, f = capa(nombre, cfgp, "F")
        fr = Image.new("RGB", (OW, OH), (205, 205, 205)); fr.paste(im, (0, 0), im)
        mx, my = int((f["x"] - x0) * kv), int((f["y"] - y0) * kv)
        mos.paste(fr.crop((mx - CW // 2, my - 70, mx + CW // 2, my - 70 + CH)), (120 + j * CW, i * CH))
mos.save(RAIZ / "_prueba21_F_antes_despues.png")
print("mosaico listo")
