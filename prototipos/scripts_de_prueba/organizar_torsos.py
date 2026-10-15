"""Copia los torsos de Higgsfield a una carpeta organizada con nombres por gesto y compara la cabeza con una referencia."""
import csv, shutil
from pathlib import Path
import numpy as np
from PIL import Image

RAIZ = Path(r"C:\Users\Juan 02\Desktop\Fase 1\Temp Real Assest Testing")
ORIGEN = RAIZ / "Torso"
DESTINO = RAIZ / "Torso Organizado"

TIPO = {"neutro": "estado", "explicar": "estado", "pulgar": "acento", "señalar": "acento",
        "bienvenida": "acento", "pregunta": "estado", "contar": "acento", "libreta": "estado"}
# clasificación por orden de nombre de archivo (marca de tiempo), revisada sobre la hoja de contactos
FRONTAL = ["pulgar", "neutro", "explicar", "señalar", "bienvenida", "libreta", "pulgar", "pulgar", "pulgar", "neutro", "explicar",
           "pulgar", "señalar", "bienvenida", "pregunta", "contar", "libreta", "neutro", "explicar", "pulgar", "señalar",
           "bienvenida", "pregunta", "libreta", "neutro", "explicar", "pulgar", "señalar", "bienvenida", "pregunta", "contar", "libreta"]
LATERAL = ["pulgar", "neutro", "explicar", "señalar", "bienvenida", "bienvenida", "bienvenida", "pregunta", "libreta", "libreta", "libreta"]

GRUPOS = [("Torso Front", FRONTAL, "frontal", "Frontal", 1), ("Torso Side", LATERAL, "tres_cuartos_izq", "Tres cuartos izquierda", 1)]
filas = []
for carpeta, gestos, prefijo, nombre_dest, ref_i in GRUPOS:
    archivos = sorted((ORIGEN / carpeta).glob("*.png"))
    assert len(archivos) == len(gestos), (carpeta, len(archivos), len(gestos))
    destino = DESTINO / nombre_dest
    destino.mkdir(parents=True, exist_ok=True)
    # referencia de cabeza: la primera imagen "neutro" del grupo
    ref = np.asarray(Image.open(archivos[gestos.index("neutro")]).convert("RGBA")).astype(np.int16)
    contador = {}
    for p, g in zip(archivos, gestos):
        contador[g] = contador.get(g, 0) + 1
        nuevo = f"{prefijo}_{g}_{contador[g]:02d}.png"
        shutil.copy2(p, destino / nuevo)
        im = np.asarray(Image.open(p).convert("RGBA")).astype(np.int16)
        # cabeza: caja del lienzo 3840x2160 (pelo, orejas, lentes y cara hasta el mentón)
        y0, y1, x0, x1 = 20, 640, 1620, 2220
        a, b = im[y0:y1, x0:x1], ref[y0:y1, x0:x1]
        valido = (a[:, :, 3] > 200) & (b[:, :, 3] > 200)
        dif = float(np.abs(a[:, :, :3] - b[:, :, :3])[valido].mean()) if valido.any() else -1
        ys, xs = np.where(im[:, :, 3] > 200)
        filas.append({"vista": nombre_dest, "gesto": g, "tipo": TIPO[g], "archivo_nuevo": nuevo, "archivo_original": f"{carpeta}/{p.name}",
                      "diferencia_cabeza": round(dif, 2), "caja_y_min": int(ys.min()), "caja_x_min": int(xs.min()), "caja_x_max": int(xs.max())})

# marca las que tienen la cabeza más alejada de la referencia (valor relativo a la mediana de su grupo)
for vista in {f["vista"] for f in filas}:
    d = np.array([f["diferencia_cabeza"] for f in filas if f["vista"] == vista])
    mediana = float(np.median(d)); umbral = max(mediana * 2.5, mediana + 4)
    for f in filas:
        if f["vista"] == vista:
            f["cabeza"] = "revisar" if f["diferencia_cabeza"] > umbral else "ok"
with open(DESTINO / "catalogo.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(filas[0].keys())); w.writeheader(); w.writerows(filas)
print("copiadas:", len(filas), "->", DESTINO)
for f in filas:
    print(f"{f['archivo_nuevo']:40s} dif_cabeza={f['diferencia_cabeza']:6.2f} {f['cabeza']}")
