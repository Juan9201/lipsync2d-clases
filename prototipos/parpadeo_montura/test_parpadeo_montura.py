"""Parpadeo alineado por la montura de las gafas: el parche cubre solo el interior de las gafas (sus bordes caen por el centro del marco
oscuro, donde el corte no se ve), no toca las cejas y encaja aunque la imagen de parpadeo no sea idéntica a la pose."""
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.biblioteca.calibraciones import importar_poses
from src.biblioteca.montura import caja_de_montura, desplazamiento_por_montura, mascara_montura
from src.biblioteca.validacion import VISEMAS

LIENZO = (320, 180)
PIEL = (230, 180, 150, 255)
MARCO = (40, 45, 100, 255)             # azul oscuro de la montura
T = 4                                  # grosor del marco


def _cara(ruta, cabeza=(160, 60), gafas=(0, 0), ojos="abiertos", cejas_arriba=0):
    """Cabeza con gafas (dos lentes con marco azul oscuro), ojos y cejas. Las gafas y las cejas pueden desplazarse por separado."""
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = cabeza
    d.rectangle((cx - 50, cy + 30, cx + 50, LIENZO[1]), fill=(245, 245, 245, 255))
    d.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=PIEL)
    gx, gy = cx + gafas[0], cy + gafas[1]
    for x0, x1 in ((gx - 36, gx - 3), (gx + 3, gx + 36)):
        d.rectangle((x0, gy - 8, x1, gy + 16), fill=PIEL, outline=MARCO, width=T)           # lente con su marco
        if ojos == "abiertos":
            d.ellipse((x0 + 9, gy, x1 - 9, gy + 11), fill=(255, 255, 255, 255))
            d.ellipse((x0 + 14, gy + 2, x1 - 14, gy + 9), fill=(70, 130, 220, 255))          # iris azul claro
        else:
            d.line((x0 + 6, gy + 7, x1 - 6, gy + 7), fill=(30, 20, 20, 255), width=2)        # párpado cerrado
    d.rectangle((gx - 34, cy - 20 - cejas_arriba, gx - 6, cy - 16 - cejas_arriba), fill=(25, 20, 20, 255))   # cejas
    d.rectangle((gx + 6, cy - 20 - cejas_arriba, gx + 34, cy - 16 - cejas_arriba), fill=(25, 20, 20, 255))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta)
    return Image.open(ruta).convert("RGBA")


def test_la_mascara_toma_el_marco_azul_oscuro_y_no_el_iris_ni_las_cejas(tmp_path):
    pose = _cara(tmp_path / "p.png")
    m = mascara_montura(pose)
    a = np.asarray(pose).astype(int)
    assert m[(a[..., 2] - a[..., 0] >= 20) & (a[..., :3].mean(2) < 100)].all()
    iris = (a[..., 0] == 70) & (a[..., 1] == 130) & (a[..., 2] == 220)
    cejas = (a[..., 0] == 25) & (a[..., 1] == 20)
    assert not m[iris].any() and not m[cejas].any() and m.sum() > 200


def test_la_caja_de_montura_va_por_el_centro_del_marco_y_deja_fuera_las_cejas(tmp_path):
    pose = _cara(tmp_path / "p.png", cabeza=(160, 60))
    x, y, w, h = caja_de_montura(pose, (110, 30, 100, 60))             # caja vieja: incluye las cejas
    # marco exterior: x 124..196, y 52..76 ; el centro del marco queda T/2 hacia dentro
    assert abs(x - (124 + T / 2)) <= 2 and abs(y - (52 + T / 2)) <= 2
    assert abs(w - (72 - T)) <= 3 and abs(h - (24 - T)) <= 3
    assert y > 40 + 12                                                   # las cejas (y 40..44) quedan fuera


def test_sin_montura_en_la_zona_no_hay_caja(tmp_path):
    im = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    assert caja_de_montura(im, (110, 30, 100, 60)) is None


def test_el_desplazamiento_recupera_cuanto_se_movio_la_imagen_de_parpadeo(tmp_path):
    pose = _cara(tmp_path / "p.png")
    parpadeo = _cara(tmp_path / "b.png", gafas=(6, -4), ojos="cerrados")      # gafas 6 px a la derecha y 4 arriba
    caja = caja_de_montura(pose, (110, 30, 100, 60))
    dx, dy = desplazamiento_por_montura(pose, parpadeo, caja)
    assert (dx, dy) == (-6, 4)                                             # lo que hay que mover la imagen para que encaje


def _importar(proyecto, blink_dir, alinear):
    base = proyecto / "Torso" / "Frontal"
    pose = _cara(base / "frontal_neutro_01.png")
    bocas = proyecto / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    formas = {v: {"x": 160, "y": 100, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    sec = {"modo": "compartido", "borde_suave_px": 6, "imagenes": {"cerrado": {"original": "cerrado.png", "desp": [0, 0]}},
           "cajas": {"frontal_neutro_01": [110, 30, 100, 60]}}
    if alinear:
        sec["alinear"] = "montura"
    cal = proyecto / "cal.json"
    cal.write_text(json.dumps({"version": 5, "juego": "frontal", "poses": {"frontal_neutro_01": {"espejo": False, "formas": formas}},
                               "parpadeo": sec}), encoding="utf-8")
    informe = importar_poses(base, proyecto, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink_dir})
    return pose, informe


def _componer_cerrado(proyecto, pose):
    carpeta = proyecto / "personajes" / "profe" / "poses" / "frontal_neutro_01"
    import yaml
    cfg = yaml.safe_load((carpeta / "config.yaml").read_text(encoding="utf-8"))["parpadeo"]
    parche = Image.open(carpeta / cfg["cerrado"]).convert("RGBA")
    salida = pose.copy()
    salida.alpha_composite(parche, (cfg["parche"]["x"], cfg["parche"]["y"]))
    return salida


def _iou(a, b):
    return (a & b).sum() / max(1, (a | b).sum())


def test_con_alinear_montura_el_marco_encaja_aunque_la_imagen_venga_desplazada_y_las_cejas_no_se_tocan(proyecto_tmp):
    blink = proyecto_tmp / "Torso" / "Blink"
    _cara(blink / "cerrado.png", gafas=(7, -5), ojos="cerrados", cejas_arriba=6)   # gafas movidas y cejas distintas
    pose, informe = _importar(proyecto_tmp, blink, alinear=True)
    assert not [a for a in informe.avisos if "parpadeo" in a]
    cerrada = _componer_cerrado(proyecto_tmp, pose)
    assert _iou(mascara_montura(cerrada), mascara_montura(pose)) >= 0.92           # el marco coincide con el de la pose
    a, c = np.asarray(pose).astype(int), np.asarray(cerrada).astype(int)
    cambio = np.abs(a - c).max(2) > 0
    ys, xs = np.where(cambio)
    assert ys.min() >= 52 and ys.max() <= 76 + 2                                   # nada por encima del marco: cejas intactas
    assert (a[40:46, 124:196] == c[40:46, 124:196]).all()


def test_sin_alinear_montura_el_comportamiento_anterior_no_cambia(proyecto_tmp):
    blink = proyecto_tmp / "Torso" / "Blink"
    _cara(blink / "cerrado.png", gafas=(7, -5), ojos="cerrados")
    pose, _ = _importar(proyecto_tmp, blink, alinear=False)
    cerrada = _componer_cerrado(proyecto_tmp, pose)
    assert _iou(mascara_montura(cerrada), mascara_montura(pose)) < 0.8             # con la silueta igual, no corrige el desplazamiento


def test_si_no_se_encuentra_la_montura_avisa_y_usa_el_metodo_anterior(proyecto_tmp):
    blink = proyecto_tmp / "Torso" / "Blink"
    _cara(blink / "cerrado.png", ojos="cerrados")
    base = proyecto_tmp / "Torso" / "Frontal"
    sin_gafas = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    ImageDraw.Draw(sin_gafas).ellipse((120, 20, 200, 100), fill=PIEL)
    base.mkdir(parents=True)
    sin_gafas.save(base / "frontal_neutro_01.png")
    bocas = proyecto_tmp / "bocas"
    bocas.mkdir()
    for v in VISEMAS:
        Image.new("RGBA", (20, 10), (200, 20, 20, 255)).save(bocas / f"boca_{v}.png")
    formas = {v: {"x": 160, "y": 100, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    cal = proyecto_tmp / "cal.json"
    cal.write_text(json.dumps({"version": 5, "juego": "frontal", "poses": {"frontal_neutro_01": {"espejo": False, "formas": formas}},
                               "parpadeo": {"modo": "compartido", "borde_suave_px": 6, "alinear": "montura",
                                            "imagenes": {"cerrado": {"original": "cerrado.png", "desp": [0, 0]}},
                                            "cajas": {"frontal_neutro_01": [110, 30, 100, 60]}}}), encoding="utf-8")
    informe = importar_poses(base, proyecto_tmp, "profe", cal, {"frontal": bocas}, parpadeos={"frontal": blink})
    assert any("montura" in a for a in informe.avisos)
    assert (proyecto_tmp / "personajes" / "profe" / "poses" / "frontal_neutro_01" / "parpadeo_cerrado.png").is_file()
