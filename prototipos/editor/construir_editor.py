"""Prepara los datos del Editor de poses (bocas + parpadeo) a partir de las poses reales.

Uso (desde la raíz del proyecto):
    .venv\\Scripts\\python.exe -I prototipos\\editor\\construir_editor.py

Lee `Temp Real Assest Testing/Torso Organizado/` y escribe en `prototipos/editor/`:
  datos_editor.js        vistas, poses, desplazamiento de cabeza, cajas de ojos, calibración de partida
  img/<vista>/<pose>.jpg        pose a tamaño completo (3840x2160, fondo gris: el JPG no guarda transparencia)
  mini/<vista>/<pose>.jpg       la misma a 1/3, para la cuadrícula «todas de un vistazo»
  blink/<vista>/<nombre>.jpg    imágenes de parpadeo (cerrado y medio)
Las imágenes no se versionan (están en .gitignore); este script las vuelve a crear.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from src.alineacion import centro_cabeza  # noqa: E402

SALIDA = Path(__file__).resolve().parent
TORSOS = RAIZ / "Temp Real Assest Testing" / "Torso Organizado"
CAL34 = RAIZ / "prototipos" / "calibradores" / "Calibrador4" / "calibraciones_34_todas_v3.json"
FONDO = (88, 94, 104)
VISEMAS = "ABCDEFGHX"

VISTAS = {
    "frontal": {"titulo": "Frontal", "poses": TORSOS / "Frontal", "bocas": "../bocas/frontal/boca_{}.png",
                "blink_cerrado": TORSOS / "Frontal Blink" / "Frontal_Blink_Full.png",        # versión del 2026-10-24 (antes: Frontal_Blink_Color.png)
                "blink_medio": TORSOS / "Frontal Blink" / "Frontal_Blink_Middle.png"},
    "tres_cuartos_der": {"titulo": "3/4 derecha", "poses": TORSOS / "Tres cuartos derecha",
                         "bocas": "../bocas/tres_cuartos/boca34_{}.png",
                         "blink_por_pose": TORSOS / "Tres cuartos derecha Blink Organizado",
                         "excluir": "eye_contact"},               # las poses con contacto visual van en su propia vista
    # Poses 3/4 que miran a la cámara (archivos *_eye_contact.png): son redibujos completos, así que cada una necesita su propia
    # calibración de boca. Sin parpadeo por ahora. Parte de la calibración de su pose gemela (la misma sin el sufijo).
    "tres_cuartos_der_eye_contact": {"titulo": "3/4 derecha · contacto visual", "poses": TORSOS / "Tres cuartos derecha",
                                     "bocas": "../bocas/tres_cuartos/boca34_{}.png", "solo": "eye_contact"},
}


def sobre_fondo(ruta: Path) -> Image.Image:
    im = Image.open(ruta).convert("RGBA")
    base = Image.new("RGBA", im.size, FONDO + (255,))
    base.alpha_composite(im)
    return base.convert("RGB")


def guardar(im: Image.Image, destino: Path, escala: float = 1.0, calidad: int = 86):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if escala != 1.0:
        im = im.resize((round(im.width * escala), round(im.height * escala)), Image.LANCZOS)
    im.save(destino, quality=calidad)


def caja_ojos(ruta: Path):
    """Recuadro [x, y, w, h] de los ojos de una pose: la montura azul marino de las gafas, con margen
    para cejas y párpados. Sirve de partida; en el editor se ajusta a mano."""
    a = np.asarray(Image.open(ruta).convert("RGB"), dtype=np.int16)[:700]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    ys, xs = np.where((b > r + 25) & (b < 170) & (r < 110) & (g < 120))
    if not len(xs):
        return [1650, 300, 520, 200]
    x0, x1 = np.percentile(xs, [1, 99]); y0, y1 = np.percentile(ys, [1, 99])
    return [int(x0 - 26), int(y0 - 80), int(x1 - x0 + 52), int(y1 - y0 + 110)]


def pequeno(ruta: Path):
    with Image.open(ruta) as im:
        return im.convert("RGBA").resize((960, 540), Image.BILINEAR)


def construir():
    datos = {"lienzo": [3840, 2160], "vistas": {}, "precarga": {}}
    previo = json.loads(CAL34.read_text(encoding="utf-8")) if CAL34.is_file() else {"poses": {}}
    for vid, cfg in VISTAS.items():
        archivos = sorted(f for f in cfg["poses"].glob("*.png")
                          if ("solo" not in cfg or cfg["solo"] in f.stem)
                          and ("excluir" not in cfg or cfg["excluir"] not in f.stem))
        if not archivos:
            raise SystemExit(f"No hay poses en {cfg['poses']}")
        centros = {}
        for f in archivos:
            with Image.open(f) as im:
                centros[f.stem] = centro_cabeza(im.convert("RGBA"))
        ref = next((n for n in centros if "_neutro_01" in n), sorted(centros)[0])
        poses = []
        for f in archivos:
            n = f.stem
            guardar(sobre_fondo(f), SALIDA / "img" / vid / f"{n}.jpg")
            guardar(sobre_fondo(f), SALIDA / "mini" / vid / f"{n}.jpg", 1 / 3, 80)
            dx, dy = (round(centros[n][0] - centros[ref][0], 1), round(centros[n][1] - centros[ref][1], 1))
            poses.append({"nombre": n, "archivo": f"img/{vid}/{n}.jpg", "mini": f"mini/{vid}/{n}.jpg", "dcab": [dx, dy],
                          "centro": [round(centros[n][0], 1), round(centros[n][1], 1)],
                          "caja": caja_ojos(f)})
        vista = {"titulo": cfg["titulo"], "bocas": cfg["bocas"], "referencia": ref, "poses": poses, "parpadeo": None,
                 "centro_ref": [round(centros[ref][0], 1), round(centros[ref][1], 1)],
                 "caja_ref": caja_ojos(cfg["poses"] / f"{ref}.png")}

        def centro_de(ruta):
            with Image.open(ruta) as im:
                c = centro_cabeza(im.convert("RGBA"))
            return [round(c[0], 1), round(c[1], 1)]

        if "blink_cerrado" in cfg:                      # un solo juego de parpadeo para toda la vista
            imagenes = {}
            for clave, ruta in (("cerrado", cfg["blink_cerrado"]), ("medio", cfg["blink_medio"])):
                guardar(sobre_fondo(ruta), SALIDA / "blink" / vid / f"{clave}.jpg")
                imagenes[clave] = {"archivo": f"blink/{vid}/{clave}.jpg", "centro": centro_de(ruta), "original": ruta.name}
            vista["parpadeo"] = {"modo": "compartido", "imagenes": imagenes}
            print(f"{vid}: parpadeo compartido (cerrado y medio), caja de ojos {vista['caja_ref']}")
        elif "blink_por_pose" in cfg:                   # un parpadeo por pose
            imagenes = {}
            for f in archivos:
                b = cfg["blink_por_pose"] / f"{f.stem}_parpadeo.png"
                if not b.is_file():
                    print(f"  aviso: {f.stem} no tiene parpadeo")
                    continue
                guardar(sobre_fondo(b), SALIDA / "blink" / vid / f"{f.stem}_cerrado.jpg")
                imagenes[f.stem] = {"archivo": f"blink/{vid}/{f.stem}_cerrado.jpg", "centro": centro_de(b), "original": b.name}
            vista["parpadeo"] = {"modo": "por_pose", "imagenes": imagenes}
            print(f"{vid}: {len(imagenes)} parpadeos, uno por pose, caja de ojos {vista['caja_ref']}")
        datos["vistas"][vid] = vista

    for nombre, p in previo.get("poses", {}).items():       # calibración 3/4 aprobada (nombres cortos -> ids completos)
        completo = f"tres_cuartos_der_{nombre}"
        datos["precarga"][completo] = {"espejo": bool(p.get("espejo", False)), "formas": p["formas"]}
    # las poses con contacto visual parten de la calibración de su gemela, movida lo que se movió la cabeza
    v_ec, v_base = datos["vistas"].get("tres_cuartos_der_eye_contact"), datos["vistas"].get("tres_cuartos_der")
    if v_ec and v_base:
        centros_base = {p["nombre"]: p["centro"] for p in v_base["poses"]}
        for pose in v_ec["poses"]:
            base = re.sub(r"_eye_contacts?$", "", pose["nombre"])
            if base in datos["precarga"] and base in centros_base:
                dx, dy = pose["centro"][0] - centros_base[base][0], pose["centro"][1] - centros_base[base][1]
                b = datos["precarga"][base]
                datos["precarga"][pose["nombre"]] = {"espejo": b["espejo"], "estado": "her", "formas": {
                    v: {**f, "x": round(f["x"] + dx, 1), "y": round(f["y"] + dy, 1)} for v, f in b["formas"].items()}}
                print(f"  {pose['nombre']}: parte de la calibración de {base} (cabeza movida {dx:+.1f}, {dy:+.1f} px)")
    (SALIDA / "datos_editor.js").write_text("const DATOS = " + json.dumps(datos, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"datos_editor.js listo: {sum(len(v['poses']) for v in datos['vistas'].values())} poses, "
          f"{len(datos['precarga'])} calibradas de partida")


if __name__ == "__main__":
    construir()
