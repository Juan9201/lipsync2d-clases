"""FR-081: el escenario reconstruido no tiene huecos donde estaba el personaje."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.errores import AssetInvalido, EntornoIncompleto
from src.prep.inpainting import crear_escenario

RAIZ = Path(__file__).resolve().parents[2]


def test_sin_mascara_explica_que_hacer(proyecto_tmp):
    original = proyecto_tmp / "entrada" / "o.png"
    Image.new("RGB", (64, 36)).save(original)
    with pytest.raises(AssetInvalido) as exc:
        crear_escenario(original, proyecto_tmp / "no_hay.png", proyecto_tmp / "escenarios" / "E1" / "fondo.png",
                        raiz=proyecto_tmp)
    assert "máscara" in str(exc.value).lower() and "Qué hacer" in str(exc.value)


def test_sin_el_grupo_de_preparacion_sugiere_instalarlo(proyecto_tmp):
    original = proyecto_tmp / "entrada" / "o.png"
    mascara = proyecto_tmp / "entrada" / "m.png"
    Image.new("RGB", (64, 36)).save(original)
    Image.new("L", (64, 36), 255).save(mascara)
    with pytest.raises(EntornoIncompleto) as exc:
        crear_escenario(original, mascara, proyecto_tmp / "escenarios" / "E1" / "fondo.png", raiz=proyecto_tmp)
    assert "-Preparacion" in str(exc.value)


@pytest.mark.lento
@pytest.mark.integracion
def test_lama_rellena_el_hueco_sin_dejar_el_color_del_objeto(proyecto_tmp):
    modelo = RAIZ / "modelos" / "prep" / "torch" / "hub" / "checkpoints" / "big-lama.pt"
    if not (modelo.exists() and (RAIZ / ".venv-prep").exists()):
        pytest.skip("falta el grupo de preparación")
    ancho, alto = 320, 192
    degradado = np.tile(np.linspace(80, 180, ancho, dtype=np.uint8), (alto, 1))
    fondo = np.stack([degradado, degradado, np.full_like(degradado, 200)], axis=2)
    fondo[60:130, 120:200] = (255, 0, 0)                             # el "personaje"
    original = proyecto_tmp / "entrada" / "o.png"
    Image.fromarray(fondo).save(original)
    mascara = np.zeros((alto, ancho), np.uint8)
    mascara[60:130, 120:200] = 255
    ruta_m = proyecto_tmp / "entrada" / "m.png"
    Image.fromarray(mascara).save(ruta_m)
    destino = proyecto_tmp / "escenarios" / "E1_x" / "fondo.png"
    crear_escenario(original, ruta_m, destino, margen_px=3, raiz=RAIZ)
    with Image.open(destino) as res:
        assert res.mode == "RGB" and res.size == (ancho, alto)           # opaco: sin huecos
        zona = np.asarray(res)[70:120, 130:190].astype(int)
    rojo_residual = ((zona[:, :, 0] > 200) & (zona[:, :, 1] < 60)).mean()
    assert rojo_residual < 0.02
