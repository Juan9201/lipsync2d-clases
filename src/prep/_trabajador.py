"""Trabajador de preparación: se ejecuta con el Python de .venv-prep (rembg, PyTorch, OpenCV).
No importa nada del proyecto: lo lanza src/prep/entorno_prep.py con subprocess.

  python _trabajador.py segmentar ENTRADA MASCARA_SALIDA --modelo birefnet-general
  python _trabajador.py inpaint   ENTRADA MASCARA SALIDA --margen 15
"""
import argparse
import os
import sys
from pathlib import Path

from PIL import Image


def segmentar(entrada: Path, salida: Path, modelo: str) -> None:
    from rembg import new_session, remove
    sesion = new_session(modelo, providers=["CPUExecutionProvider"])
    with Image.open(entrada) as im:
        mascara = remove(im.convert("RGB"), session=sesion, only_mask=True)
    mascara.convert("L").save(salida)


def inpaint(entrada: Path, mascara: Path, salida: Path, margen: int) -> None:
    import cv2
    import numpy as np
    import torch
    from simple_lama_inpainting.utils import prepare_img_and_mask

    modelo_ruta = os.environ.get("LAMA_MODEL")
    if not modelo_ruta or not Path(modelo_ruta).is_file():
        raise FileNotFoundError(f"Falta el modelo LaMa ({modelo_ruta})")
    with Image.open(entrada) as im:
        imagen = im.convert("RGB")
    m = np.asarray(Image.open(mascara).convert("L")) > 127
    kernel = np.ones((2 * margen + 1, 2 * margen + 1), np.uint8)
    dilatada = cv2.dilate(m.astype(np.uint8) * 255, kernel)         # margen para tapar el borde
    # El modelo TorchScript trae constantes CUDA: hay que cargarlo con map_location="cpu".
    modelo = torch.jit.load(modelo_ruta, map_location="cpu")
    modelo.eval()
    img_t, mask_t = prepare_img_and_mask(imagen, Image.fromarray(dilatada), torch.device("cpu"))
    with torch.inference_mode():
        resultado = modelo(img_t, mask_t)[0].permute(1, 2, 0).numpy()
    Image.fromarray(np.clip(resultado * 255, 0, 255).astype(np.uint8)).save(salida)


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("segmentar")
    s.add_argument("entrada", type=Path); s.add_argument("salida", type=Path)
    s.add_argument("--modelo", default="birefnet-general")
    i = sub.add_parser("inpaint")
    i.add_argument("entrada", type=Path); i.add_argument("mascara", type=Path); i.add_argument("salida", type=Path)
    i.add_argument("--margen", type=int, default=15)
    a = p.parse_args()
    if a.orden == "segmentar":
        segmentar(a.entrada, a.salida, a.modelo)
    else:
        inpaint(a.entrada, a.mascara, a.salida, a.margen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
