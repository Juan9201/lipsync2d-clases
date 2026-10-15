"""Bocas y poses placeholder generadas por código (FR-060): sirven para probar el pipeline
sin los assets definitivos."""
from pathlib import Path
from typing import Tuple

import yaml
from PIL import Image, ImageDraw

VISEMAS = "ABCDEFGHX"
LABIO = (150, 40, 50, 255)
INTERIOR = (60, 10, 20, 255)
DIENTES = (245, 245, 240, 255)
LENGUA = (210, 90, 100, 255)


def dibujar_boca(visema: str, tam: Tuple[int, int] = (256, 160)) -> Image.Image:
    """Una forma geométrica por visema, centrada en la imagen."""
    w, h = tam
    im = Image.new("RGBA", tam, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = w // 2, h // 2

    def elipse(rx, ry, relleno=INTERIOR):
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=relleno, outline=LABIO, width=6)

    if visema == "A":      # labios cerrados y apretados
        d.rectangle((cx - 70, cy - 5, cx + 70, cy + 5), fill=LABIO)
    elif visema == "X":    # reposo: línea fina
        d.rectangle((cx - 60, cy - 2, cx + 60, cy + 2), fill=LABIO)
    elif visema == "B":    # dientes juntos, algo abierta
        d.rounded_rectangle((cx - 70, cy - 16, cx + 70, cy + 16), 10, fill=DIENTES, outline=LABIO, width=6)
    elif visema == "C":    # abierta a media altura
        elipse(60, 32)
    elif visema == "D":    # muy abierta
        elipse(62, 58)
    elif visema == "E":    # redondeada media
        elipse(38, 38)
    elif visema == "F":    # labios fruncidos
        elipse(20, 20)
    elif visema == "G":    # dientes superiores sobre el labio inferior
        d.rounded_rectangle((cx - 60, cy - 22, cx + 60, cy + 22), 10, fill=INTERIOR, outline=LABIO, width=6)
        d.rectangle((cx - 50, cy - 18, cx + 50, cy - 2), fill=DIENTES)
    elif visema == "H":    # lengua alta
        elipse(58, 40)
        d.ellipse((cx - 28, cy - 18, cx + 28, cy + 14), fill=LENGUA)
    return im


def crear_ojos_placeholder(carpeta: Path, ancho_ojos: int) -> None:
    """Parche de ojos cerrados de prueba."""
    ojos = Image.new("RGBA", (ancho_ojos, max(int(ancho_ojos * 0.4), 2)), (230, 180, 150, 255))
    do = ImageDraw.Draw(ojos)
    for fx in (0.28, 0.72):
        x = int(ancho_ojos * fx)
        do.line((x - 12, ojos.height // 2, x + 12, ojos.height // 2), fill=(60, 30, 20, 255), width=4)
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    ojos.save(Path(carpeta) / "ojos_cerrados.png")


def crear_ojos_desde_imagen(imagen: Image.Image, cx: float, cy: float, ancho: int, destino: Path) -> Path:
    """Párpado de prueba generado de la propia imagen: un óvalo del color de piel sobre cada ojo
    (a ±0,3 del ancho del ancla) con una línea de pestañas. No cubre la montura de los lentes."""
    import numpy as np
    from PIL import ImageFilter
    rgb = imagen.convert("RGB")
    alto = max(int(ancho * 0.4), 4)
    # Color de piel: mediana de los píxeles "piel" (R > G > B, claros) de la zona de los ojos
    zona = np.asarray(rgb.crop((int(cx - ancho), int(cy - alto), int(cx + ancho), int(cy + alto)))).reshape(-1, 3).astype(int)
    piel_mask = (zona[:, 0] > zona[:, 1]) & (zona[:, 1] > zona[:, 2]) & (zona[:, 0] > 150) & (zona[:, 0] - zona[:, 2] > 30)
    piel = tuple(int(v) for v in np.median(zona[piel_mask], axis=0)) if piel_mask.any() else (225, 175, 140)
    mascara = Image.new("L", (ancho, alto), 0)
    dm = ImageDraw.Draw(mascara)
    rx, ry = ancho * 0.20, alto * 0.30
    parche = Image.new("RGBA", (ancho, alto), (*piel, 0))
    dp = ImageDraw.Draw(parche)
    for fx in (0.2, 0.8):
        x, y = ancho * fx, alto / 2
        dm.ellipse((x - rx, y - ry, x + rx, y + ry), fill=255)
        dp.line((x - rx * 0.8, y + 1, x + rx * 0.8, y + 1), fill=(70, 45, 40, 255), width=max(ancho // 50, 1))
    mascara = mascara.filter(ImageFilter.GaussianBlur(max(ancho / 70, 0.8)))
    lineas = np.asarray(parche)[:, :, 3] > 0                      # las pestañas conservan su opacidad
    parche = Image.composite(Image.new("RGBA", parche.size, (*piel, 255)), parche, mascara)
    arr = np.asarray(parche).copy()
    arr[:, :, 3] = np.maximum(arr[:, :, 3] * (np.asarray(mascara) / 255.0), np.where(lineas, 255, 0)).astype(np.uint8)
    Image.fromarray(arr, "RGBA").save(destino)
    return Path(destino)


def crear_bocas_placeholder(carpeta: Path, tam: Tuple[int, int] = (256, 160)) -> None:
    """Las nueve bocas de prueba en <carpeta>/bocas/."""
    destino = Path(carpeta) / "bocas"
    destino.mkdir(parents=True, exist_ok=True)
    for v in VISEMAS:
        dibujar_boca(v, tam).save(destino / f"{v}.png")


def crear_pose_placeholder(carpeta: Path, id_pose: str, lienzo: Tuple[int, int] = (1920, 1080)) -> Path:
    """Crea una pose completa de prueba (cuerpo geométrico, ojos cerrados, 9 bocas, config.yaml)."""
    carpeta = Path(carpeta)
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    w, h = lienzo
    cuerpo = Image.new("RGBA", lienzo, (0, 0, 0, 0))
    d = ImageDraw.Draw(cuerpo)
    cx = int(w * 0.70)
    d.rounded_rectangle((cx - int(w * 0.13), int(h * 0.40), cx + int(w * 0.13), h), 30, fill=(245, 245, 245, 255))
    d.ellipse((cx - int(h * 0.14), int(h * 0.08), cx + int(h * 0.14), int(h * 0.42)), fill=(230, 180, 150, 255))
    ojos_y = int(h * 0.22)
    for dx in (-int(h * 0.05), int(h * 0.05)):
        d.ellipse((cx + dx - 8, ojos_y - 8, cx + dx + 8, ojos_y + 8), fill=(30, 30, 30, 255))
    cuerpo.save(carpeta / "cuerpo.png")

    ancho_ojos = int(h * 0.20)
    crear_ojos_placeholder(carpeta, ancho_ojos)
    crear_bocas_placeholder(carpeta)

    config = {
        "version": 1, "id": id_pose, "nombre": "placeholder", "lienzo": [w, h], "espejo": False,
        "bocas_de": None,
        "anclas": {
            "boca": {"x": cx, "y": int(h * 0.34), "ancho": int(h * 0.12), "angulo": 0.0},
            "ojos": {"x": cx, "y": ojos_y, "ancho": ancho_ojos, "angulo": 0.0},
            "cabeza": {"x": cx, "y": int(h * 0.25)},
        },
    }
    (carpeta / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return carpeta
