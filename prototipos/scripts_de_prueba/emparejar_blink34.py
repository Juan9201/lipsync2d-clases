"""Empareja cada parpadeo 3/4 con su pose (por parecido fuera de los ojos) y compara con el orden secuencial."""
import csv, shutil
from pathlib import Path
import numpy as np
from PIL import Image

R = Path(r"C:\Users\Juan 02\Desktop\Fase 1\Temp Real Assest Testing\Torso Organizado")
BL = sorted((R / "Tres cuartos derecha Blink").glob("*.png"))
POSES = sorted((R / "Tres cuartos derecha").glob("tres_cuartos_der_*.png"))
# orden secuencial = orden de los originales de Higgsfield (el mismo con el que se nombraron las poses)
filas = list(csv.DictReader(open(R / "catalogo.csv", encoding="utf-8-sig")))
secuencia = [f["archivo_nuevo"] for f in filas if f["vista"] == "Tres cuartos derecha"]
print("orden secuencial de poses:", [s.replace("tres_cuartos_der_", "").replace(".png", "") for s in secuencia])


def cargar(p):
    im = Image.open(p).convert("RGBA").resize((960, 540), Image.BILINEAR)
    return np.asarray(im).astype(np.int16)


P = {p.name: cargar(p) for p in POSES}
B = [cargar(b) for b in BL]
# máscara: se excluye la banda de la cara donde viven ojos y cejas
excl = np.zeros((540, 960), bool); excl[40:170, 330:640] = True
D = np.zeros((len(B), len(secuencia)))
for i, b in enumerate(B):
    for j, n in enumerate(secuencia):
        o = P[n]; v = (o[:, :, 3] > 200) & (b[:, :, 3] > 200) & ~excl
        D[i, j] = np.abs(o[:, :, :3] - b[:, :, :3])[v].mean() if v.sum() > 1000 else 999
mejor = D.argmin(1)
ok = 0
for i, b in enumerate(BL):
    m = int(mejor[i]); orden = i
    s2 = np.sort(D[i])[1]
    print(f"{i+1:2d}. {b.name[:24]}  mejor pose: {secuencia[m].replace('tres_cuartos_der_','').replace('.png',''):16s} dif {D[i,m]:5.2f} (2.ª {s2:5.2f})  | secuencial: {secuencia[orden].replace('tres_cuartos_der_','').replace('.png',''):16s} dif {D[i,orden]:5.2f}  {'OK' if m == orden else 'DIFIERE'}")
    ok += m == orden
print("coinciden con el orden secuencial:", ok, "de", len(BL))
np.save(R / "_blink34_difs.npy", D)
