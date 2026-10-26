"""«Actualizar poses»: copia al render las imágenes corregidas con el mismo nombre solo si la cara quedó en su sitio."""
import yaml
from PIL import Image, ImageDraw

from src import poses_fuente


def _imagen(ruta, cara=(700, 500), color=(200, 150, 100)):
    im = Image.new("RGB", (1400, 1000), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse([cara[0] - 90, cara[1] - 120, cara[0] + 90, cara[1] + 120], fill=color)       # la cara
    d.ellipse([cara[0] - 30, cara[1] - 30, cara[0] - 10, cara[1] - 10], fill=(0, 0, 0))     # un ojo (da relieve a la búsqueda)
    d.rectangle([cara[0] + 10, cara[1] + 20, cara[0] + 50, cara[1] + 30], fill=(80, 40, 40))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta)


def _proyecto(tmp_path):
    poses = tmp_path / "personajes" / "profesor" / "poses" / "frontal_pregunta_01"
    _imagen(poses / "cuerpo.png")
    (poses / "config.yaml").write_text(yaml.safe_dump({"formas": {"A": {"x": 700.0, "y": 500.0}}}), encoding="utf-8")
    return tmp_path / poses_fuente.ORIGEN / "Frontal"


def test_una_imagen_igual_no_aparece(tmp_path):
    fuente = _proyecto(tmp_path)
    _imagen(fuente / "frontal_pregunta_01.png")
    assert poses_fuente.revisar(tmp_path) == []


def test_una_imagen_corregida_con_la_cara_en_su_sitio_se_actualiza_y_se_respalda(tmp_path):
    fuente = _proyecto(tmp_path)
    _imagen(fuente / "frontal_pregunta_01.png")
    ImageDraw.Draw(Image.open(fuente / "frontal_pregunta_01.png")).point([(1, 1)])
    nueva = Image.open(fuente / "frontal_pregunta_01.png"); ImageDraw.Draw(nueva).rectangle([100, 800, 200, 900], fill=(0, 0, 255)); nueva.save(fuente / "frontal_pregunta_01.png")
    assert [c["estado"] for c in poses_fuente.revisar(tmp_path)] == ["actualizable"]
    r = poses_fuente.actualizar(tmp_path)
    assert r["actualizadas"] == ["frontal_pregunta_01"] and r["pendientes"] == []
    destino = tmp_path / "personajes" / "profesor" / "poses" / "frontal_pregunta_01" / "cuerpo.png"
    assert Image.open(destino).getpixel((150, 850)) == (0, 0, 255)
    assert (next((tmp_path / "respaldo_poses").iterdir()) / "frontal_pregunta_01" / "cuerpo.png").is_file()
    assert poses_fuente.revisar(tmp_path) == []


def test_si_la_cara_se_movio_no_se_toca_nada(tmp_path):
    fuente = _proyecto(tmp_path)
    _imagen(fuente / "frontal_pregunta_01.png", cara=(715, 506))
    antes = (tmp_path / "personajes" / "profesor" / "poses" / "frontal_pregunta_01" / "cuerpo.png").read_bytes()
    c = poses_fuente.revisar(tmp_path)
    assert [x["estado"] for x in c] == ["cara_movida"]
    r = poses_fuente.actualizar(tmp_path)
    assert r["actualizadas"] == [] and len(r["pendientes"]) == 1
    assert (tmp_path / "personajes" / "profesor" / "poses" / "frontal_pregunta_01" / "cuerpo.png").read_bytes() == antes


def test_nuevas_y_nombres_invalidos_se_avisan_pero_no_se_importan(tmp_path):
    fuente = _proyecto(tmp_path)
    _imagen(fuente / "frontal_nueva_01.png")
    _imagen(fuente / "frontal_contar_01-01.png")
    _imagen(tmp_path / poses_fuente.ORIGEN / "Frontal Blink" / "frontal_neutro_01.png")           # las carpetas de parpadeo se ignoran
    assert {c["pose"]: c["estado"] for c in poses_fuente.revisar(tmp_path)} == {"frontal_nueva_01": "nueva", "frontal_contar_01-01": "nombre_invalido"}
