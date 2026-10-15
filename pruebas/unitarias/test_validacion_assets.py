"""FR-061: validación de assets antes de renderizar, con mensajes accionables."""
import pytest
import yaml
from PIL import Image

from src.biblioteca.validacion import validar_escenario, validar_pose
from src.errores import AssetInvalido

VISEMAS = "ABCDEFGHX"
LIENZO = (320, 180)


def _png(ruta, tam, modo="RGBA"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.new(modo, tam, (200, 100, 100, 255) if modo == "RGBA" else (200, 100, 100)).save(ruta)


@pytest.fixture
def pose_ok(proyecto_tmp):
    ruta = proyecto_tmp / "personajes" / "p" / "poses" / "P1_base"
    cfg = {"version": 1, "id": "P1", "lienzo": list(LIENZO), "espejo": False,
           "anclas": {"boca": {"x": 100, "y": 100, "ancho": 30, "angulo": 0},
                      "ojos": {"x": 100, "y": 80, "ancho": 40, "angulo": 0},
                      "cabeza": {"x": 100, "y": 90}}}
    ruta.mkdir(parents=True)
    (ruta / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _png(ruta / "cuerpo.png", LIENZO)
    _png(ruta / "ojos_cerrados.png", (40, 20))
    for v in VISEMAS:
        _png(ruta / "bocas" / f"{v}.png", (64, 40))
    return ruta


def test_pose_correcta_pasa(pose_ok):
    validar_pose(pose_ok)  # no lanza


def test_falta_una_boca_nombra_el_archivo(pose_ok):
    (pose_ok / "bocas" / "F.png").unlink()
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "F.png" in str(exc.value) and "Qué hacer" in str(exc.value)


def test_boca_sin_alfa(pose_ok):
    _png(pose_ok / "bocas" / "C.png", (64, 40), modo="RGB")
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "C.png" in str(exc.value) and "transparencia" in str(exc.value)


def test_bocas_de_distinto_tamano(pose_ok):
    _png(pose_ok / "bocas" / "D.png", (70, 40))
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "D.png" in str(exc.value) and "tamaño" in str(exc.value)


def test_cuerpo_con_tamano_distinto_al_lienzo(pose_ok):
    _png(pose_ok / "cuerpo.png", (300, 180))
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "cuerpo.png" in str(exc.value)


def test_falta_ojos_cerrados(pose_ok):
    (pose_ok / "ojos_cerrados.png").unlink()
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "ojos_cerrados.png" in str(exc.value)


def test_bocas_de_reutiliza_bocas_de_otra_pose(pose_ok, proyecto_tmp):
    otra = pose_ok.parent / "P2_brazos"
    otra.mkdir()
    cfg = yaml.safe_load((pose_ok / "config.yaml").read_text(encoding="utf-8"))
    cfg.update(id="P2", bocas_de="P1")
    (otra / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _png(otra / "cuerpo.png", LIENZO)
    validar_pose(otra)  # las bocas y los ojos salen de P1


def test_bocas_de_inexistente(pose_ok):
    cfg = yaml.safe_load((pose_ok / "config.yaml").read_text(encoding="utf-8"))
    cfg.update(bocas_de="P9")
    (pose_ok / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "P9" in str(exc.value)


def test_escenario_16_9_correcto(proyecto_tmp):
    ruta = proyecto_tmp / "escenarios" / "E1_salon"
    _png(ruta / "fondo.png", (320, 180), modo="RGB")
    validar_escenario(ruta, salida=(160, 90))


def test_escenario_no_16_9(proyecto_tmp):
    ruta = proyecto_tmp / "escenarios" / "E1_salon"
    _png(ruta / "fondo.png", (400, 300), modo="RGB")
    with pytest.raises(AssetInvalido) as exc:
        validar_escenario(ruta, salida=(160, 90))
    assert "16:9" in str(exc.value)


def test_escenario_sin_fondo(proyecto_tmp):
    ruta = proyecto_tmp / "escenarios" / "E1_salon"
    ruta.mkdir(parents=True)
    with pytest.raises(AssetInvalido) as exc:
        validar_escenario(ruta, salida=(160, 90))
    assert "fondo.png" in str(exc.value)


def test_ojos_de_toma_los_ojos_de_otra_pose_y_las_bocas_de_la_propia(pose_ok):
    """Pose con gafas y pose sin gafas: misma boca, ojos distintos."""
    sin_gafas = pose_ok.parent / "P2_sin_gafas"
    cfg = yaml.safe_load((pose_ok / "config.yaml").read_text(encoding="utf-8"))
    cfg.update(id="P2", ojos_de=None)
    sin_gafas.mkdir()
    (sin_gafas / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _png(sin_gafas / "cuerpo.png", LIENZO)
    _png(sin_gafas / "ojos_cerrados.png", (40, 20))
    cfg["bocas_de"] = "P1"
    (sin_gafas / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    validar_pose(sin_gafas)      # bocas de P1, ojos propios


def test_ojos_de_inexistente(pose_ok):
    cfg = yaml.safe_load((pose_ok / "config.yaml").read_text(encoding="utf-8"))
    cfg.update(ojos_de="P9")
    (pose_ok / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(pose_ok)
    assert "P9" in str(exc.value) and "ojos" in str(exc.value).lower()
