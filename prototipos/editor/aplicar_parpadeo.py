"""Aplica el parpadeo ESTÁNDAR (contorno del rostro, de pelo a quijada) a las poses de una vista, sin tocar las bocas.

    .venv\\Scripts\\python.exe -I prototipos\\editor\\aplicar_parpadeo.py [--calibracion JSON] [--referencia POSE] [--vista frontal]

1. Copia de seguridad de lo que hay (config.yaml y parpadeo_*.png de cada pose) en respaldo_parpadeo/<fecha>_antes_de_aplicar/.
2. Toma del JSON del editor la caja del rostro de la pose de referencia (por defecto frontal_bienvenida_01: del pelo a la quijada) y la lleva a
   cada pose según dónde tiene la cabeza (todas las poses frontales comparten la misma cabeza; solo cambia dónde cae).
3. Importa solo el parpadeo (imágenes y desplazamientos del JSON) con la máscara de contorno. La calibración de boca que cada pose YA tiene se
   le pasa al importador tal cual, así que las bocas no cambian; se comprueba al final.
Deja el JSON usado en prototipos/editor/calibraciones/versiones/<nombre>/ para poder repetirlo."""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from src.alineacion import centro_cabeza  # noqa: E402
from src.biblioteca.calibraciones import importar_poses  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibracion", type=Path, default=RAIZ / "prototipos" / "editor" / "calibraciones" / "versiones" / "V3_parpadeo" / "calibracion_frontal.json")
    ap.add_argument("--referencia", default="frontal_bienvenida_01", help="Pose cuya caja de rostro (pelo a quijada) se lleva a todas")
    ap.add_argument("--vista", default="frontal")
    ap.add_argument("--blink", type=Path, default=RAIZ / "Temp Real Assest Testing" / "Torso Organizado" / "Frontal Blink")
    ap.add_argument("--personaje", default="profesor")
    ap.add_argument("--nombre", default="V3_contorno", help="Carpeta de versiones donde se guarda el JSON usado")
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    a = ap.parse_args()

    poses_dir = a.raiz / "personajes" / a.personaje / "poses"
    cal = json.loads(a.calibracion.read_text(encoding="utf-8"))
    cajas = cal["parpadeo"]["cajas"]
    if a.referencia not in cajas:
        print(f"ERROR: la pose de referencia {a.referencia} no está en el JSON. Qué hacer: elige una de {sorted(cajas)[:3]}…"); return 1
    ids = sorted(p for p in cajas if (poses_dir / p / "cuerpo.png").is_file())

    # 1) copia de seguridad
    copia = a.raiz / "respaldo_parpadeo" / (time.strftime("%Y-%m-%d_%H%M") + "_antes_de_aplicar")
    for i in ids:
        (copia / i).mkdir(parents=True, exist_ok=True)
        for f in ("config.yaml", "parpadeo_cerrado.png", "parpadeo_medio.png"):
            if (poses_dir / i / f).is_file():
                shutil.copy2(poses_dir / i / f, copia / i / f)
    print(f"copia de seguridad: {copia}")

    # 2) la caja de rostro de la referencia, llevada a cada pose según su cabeza
    pelo = {i: centro_cabeza(Image.open(poses_dir / i / "cuerpo.png")) for i in ids}
    rx, ry, rw, rh = cajas[a.referencia]
    nuevas = {}
    for i in ids:
        dx, dy = pelo[i][0] - pelo[a.referencia][0], pelo[i][1] - pelo[a.referencia][1]
        nuevas[i] = [round(rx + dx), round(ry + dy), rw, rh]
    cal["parpadeo"]["cajas"] = nuevas
    cal["parpadeo"]["mascara"] = "contorno"
    cal["parpadeo"].setdefault("erosion_px", 10)

    # 3) las bocas que cada pose ya tiene se le pasan al importador tal cual
    antes = {}
    cal["poses"] = {}
    for i in ids:
        cfg = yaml.safe_load((poses_dir / i / "config.yaml").read_text(encoding="utf-8"))
        antes[i] = cfg["formas"]
        cal["poses"][i] = {"espejo": bool(cfg.get("espejo", False)), "formas": cfg["formas"]}
    guardado = a.raiz / "prototipos" / "editor" / "calibraciones" / "versiones" / a.nombre
    guardado.mkdir(parents=True, exist_ok=True)
    (guardado / "calibracion_frontal.json").write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        for i in ids:
            shutil.copyfile(poses_dir / i / "cuerpo.png", Path(tmp) / f"{i}.png")
        informe = importar_poses([Path(tmp)], a.raiz, a.personaje, guardado / "calibracion_frontal.json", None,
                                 parpadeos={a.vista: a.blink})
    for linea in informe.avisos[:8]:
        print("  aviso:", linea)
    print(f"rechazados: {len(informe.rechazados)}")

    # 4) comprobación: las bocas no cambiaron
    cambiadas = []
    for i in ids:
        despues = yaml.safe_load((poses_dir / i / "config.yaml").read_text(encoding="utf-8"))["formas"]
        if any(abs(antes[i][v][k] - despues[v][k]) > 0.01 for v in antes[i] for k in ("x", "y", "s", "r")) or any(antes[i][v]["m"] != despues[v]["m"] for v in antes[i]):
            cambiadas.append(i)
    con = sum(1 for i in ids if (poses_dir / i / "parpadeo_cerrado.png").is_file())
    print(f"poses con parpadeo: {con}/{len(ids)} · poses cuya boca cambió: {cambiadas or 'ninguna'}")
    return 0 if not cambiadas and con == len(ids) else 2


if __name__ == "__main__":
    raise SystemExit(main())
