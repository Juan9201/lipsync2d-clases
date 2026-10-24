"""Parpadeo con máscara de contorno: en lugar de pegar un rectángulo, el parche sigue la silueta de la cabeza de la pose (de pelo a quijada),
se mete `erosion_px` hacia dentro del borde y se difumina. El corte cae sobre piel con piel (sin línea recta) y el contorno oscuro de
la pose no se toca."""
import json

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from src.biblioteca.calibraciones import importar_poses
from src.biblioteca.validacion import VISEMAS

LIENZO = (320, 240)
PIEL = (230, 180, 150, 255)
PIEL_BLINK = (222, 172, 143, 255)           # la imagen de parpadeo trae la piel un poco más oscura (como pasa con las de IA)
TINTA = (20, 15, 15, 255)


def _cabeza(ruta, ojos_cerrados=False, piel=PIEL, desp=(0, 0), extra=0):
    """Cabeza redonda con contorno de tinta, ojos y camisa. Fondo transparente."""
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = 160 + desp[0], 100 + desp[1]
    d.rectangle((cx - 60, cy + 70, cx + 60, LIENZO[1]), fill=(245, 245, 245, 255))
    d.ellipse((cx - 62 - extra, cy - 72 - extra, cx + 62 + extra, cy + 72 + extra), fill=TINTA)     # contorno (la imagen de IA lo trae más grueso)
    d.ellipse((cx - 56, cy - 66, cx + 56, cy + 66), fill=piel)
    color = (30, 20, 20, 255) if ojos_cerrados else (255, 255, 255, 255)
    d.rectangle((cx - 36, cy - 12, cx - 12, cy + 2), fill=color)
    d.rectangle((cx + 12, cy - 12, cx + 36, cy + 2), fill=color)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta)
    return Image.open(ruta).convert("RGBA")


CAJA = [90, 20, 140, 140]                   # del pelo a la quijada (sin llegar a la camisa); más ancha que la cabeza en los lados


def _importar(proyecto, mascara=None, erosion=None, borde=10, por_parametro=False):
    base = proyecto / "Torso" / "Frontal"
    pose = _cabeza(base / "frontal_neutro_01.png")
    blink = proyecto / "Torso" / "Blink"
    _cabeza(blink / "cerrado.png", ojos_cerrados=True, piel=PIEL_BLINK, extra=3)
    bocas = proyecto / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    formas = {v: {"x": 160, "y": 150, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    sec = {"modo": "compartido", "borde_suave_px": borde, "imagenes": {"cerrado": {"original": "cerrado.png", "desp": [0, 0]}},
           "cajas": {"frontal_neutro_01": CAJA}}
    if mascara and not por_parametro:
        sec["mascara"] = mascara
    if erosion is not None and not por_parametro:
        sec["erosion_px"] = erosion
    cal = proyecto / "cal.json"
    cal.write_text(json.dumps({"version": 5, "juego": "frontal", "poses": {"frontal_neutro_01": {"espejo": False, "formas": formas}},
                               "parpadeo": sec}), encoding="utf-8")
    informe = importar_poses(base, proyecto, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink},
                         **({"parpadeo_mascara": mascara, "erosion_px": erosion} if por_parametro else {}))
    return pose, informe


def _cerrada(proyecto, pose):
    carpeta = proyecto / "personajes" / "profe" / "poses" / "frontal_neutro_01"
    cfg = yaml.safe_load((carpeta / "config.yaml").read_text(encoding="utf-8"))["parpadeo"]
    parche = Image.open(carpeta / cfg["cerrado"]).convert("RGBA")
    salida = pose.copy()
    salida.alpha_composite(parche, (cfg["parche"]["x"], cfg["parche"]["y"]))
    return np.asarray(salida).astype(int), np.asarray(pose).astype(int)


def test_con_contorno_no_se_toca_nada_fuera_de_la_silueta_ni_el_contorno_de_tinta(proyecto_tmp):
    pose, informe = _importar(proyecto_tmp, "contorno", erosion=8)
    assert not [a for a in informe.avisos if "parpadeo" in a]
    c, p = _cerrada(proyecto_tmp, pose)
    fuera = p[..., 3] == 0                                                           # fondo transparente de la pose
    assert (c[fuera] == p[fuera]).all()                                              # el fondo sigue transparente
    cx, cy = 160, 100
    yy, xx = np.mgrid[0:LIENZO[1], 0:LIENZO[0]]
    r = np.sqrt(((xx - cx) / 1.0) ** 2 + ((yy - cy) / 1.0) ** 2)
    contorno = (np.abs(((xx - cx) / 62) ** 2 + ((yy - cy) / 72) ** 2 - 1) < 0.03)
    assert np.abs(c[contorno] - p[contorno]).max() <= 2                              # la línea de tinta es la de la pose


def test_con_contorno_los_ojos_cerrados_llegan_completos(proyecto_tmp):
    pose, _ = _importar(proyecto_tmp, "contorno", erosion=8)
    c, p = _cerrada(proyecto_tmp, pose)
    ojo = (slice(94, 98), slice(130, 144))                                           # dentro del ojo izquierdo (con margen)
    assert (np.abs(c[ojo][..., :3] - np.array([30, 20, 20])).max() <= 3)             # tinta de ojo cerrado (de la imagen de parpadeo)
    assert (np.abs(p[ojo][..., :3] - np.array([255, 255, 255])).max() <= 3)          # la pose los tenía abiertos


def test_con_contorno_el_cambio_de_tono_de_piel_es_gradual_no_un_escalon(proyecto_tmp):
    pose, _ = _importar(proyecto_tmp, "contorno", erosion=8, borde=14)
    c, p = _cerrada(proyecto_tmp, pose)
    fila = c[100 + 40, :, :3].sum(axis=1)                                            # una fila de piel por debajo de los ojos
    paso = np.abs(np.diff(fila))[116:160].max()                                      # sin contar la línea de tinta del borde
    assert paso <= 4                                                                 # el tono baja suave hasta el de la imagen de parpadeo


def test_pidiendo_el_rectangulo_el_comportamiento_anterior_sigue_disponible(proyecto_tmp):
    pose, _ = _importar(proyecto_tmp, "rectangulo")                                  # comportamiento anterior
    c, p = _cerrada(proyecto_tmp, pose)
    cambio = np.abs(c - p).max(axis=2) > 0
    ys, xs = np.where(cambio)
    assert xs.min() >= CAJA[0] - 12 and xs.max() <= CAJA[0] + CAJA[2] + 12


def test_con_contorno_el_cambio_queda_dentro_de_la_cabeza(proyecto_tmp):
    pose, _ = _importar(proyecto_tmp, "contorno", erosion=8)
    c, p = _cerrada(proyecto_tmp, pose)
    cambio = np.abs(c - p).max(axis=2) > 0
    ys, xs = np.where(cambio)
    assert xs.min() >= 160 - 56 and xs.max() <= 160 + 56                             # más estrecho que la caja (que sobresale de la cabeza)


def test_una_mascara_desconocida_avisa_y_usa_el_rectangulo(proyecto_tmp):
    pose, informe = _importar(proyecto_tmp, "triangulo")
    assert any("mascara" in a.lower() or "máscara" in a.lower() for a in informe.avisos)
    assert (proyecto_tmp / "personajes" / "profe" / "poses" / "frontal_neutro_01" / "parpadeo_cerrado.png").is_file()


def test_la_mascara_tambien_se_puede_pedir_por_parametro_sin_tocar_el_json_del_editor(proyecto_tmp):
    pose, _ = _importar(proyecto_tmp, "contorno", erosion=8, por_parametro=True)
    c, p = _cerrada(proyecto_tmp, pose)
    assert (c[p[..., 3] == 0] == p[p[..., 3] == 0]).all()                            # igual que pidiéndola en el JSON


def test_sin_indicar_nada_el_estandar_es_el_contorno(proyecto_tmp):
    pose, _ = _importar(proyecto_tmp)                                                # el JSON no trae «mascara»
    c, p = _cerrada(proyecto_tmp, pose)
    fuera = p[..., 3] == 0
    assert (c[fuera] == p[fuera]).all()                                              # nada fuera de la silueta: es el contorno, no el rectángulo
