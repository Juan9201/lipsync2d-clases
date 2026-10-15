"""FR-064, FR-061: el importador clasifica por nombre los archivos de entrada/ y los ordena."""
from pathlib import Path

from PIL import Image

from src.biblioteca.importador import importar


def _png(ruta: Path, tam=(64, 36), modo="RGBA", alfa=255):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    color = (200, 100, 100, alfa) if modo == "RGBA" else (200, 100, 100)
    Image.new(modo, tam, color).save(ruta)


def test_clasifica_y_ordena_todos_los_tipos(proyecto_tmp):
    e = proyecto_tmp / "entrada"
    _png(e / "P1_boca_A.png", (32, 20))          # llega antes que la pose (orden alfabético)
    _png(e / "P1_ojos.png", (30, 12))
    _png(e / "P1_profesor.png", (320, 180), alfa=0)   # con transparencia real
    Image.new("RGB", (320, 180), (9, 9, 9)).save(e / "E1_salon.jpg")
    inf = importar(e, proyecto_tmp, personaje="profesor")
    pose = proyecto_tmp / "personajes" / "profesor" / "poses" / "P1_profesor"
    assert (pose / "cuerpo.png").is_file() and (pose / "config.yaml").is_file()
    assert (pose / "bocas" / "A.png").is_file() and (pose / "ojos_cerrados.png").is_file()
    assert not (proyecto_tmp / "personajes" / "profesor" / "poses" / "P1").exists()
    assert (proyecto_tmp / "escenarios" / "E1_salon" / "fondo.jpg").is_file()
    assert len(inf.importados) == 4 and not inf.rechazados


def test_pose_sin_transparencia_va_a_original_y_pide_preparacion(proyecto_tmp):
    e = proyecto_tmp / "entrada"
    Image.new("RGB", (320, 180), (1, 1, 1)).save(e / "P2_presentando.png")
    inf = importar(e, proyecto_tmp, personaje="profesor")
    pose = proyecto_tmp / "personajes" / "profesor" / "poses" / "P2_presentando"
    assert (pose / "original.png").is_file() and not (pose / "cuerpo.png").exists()
    assert any("src.prep" in a for a in inf.avisos)


def test_rechaza_boca_sin_transparencia_y_nombres_desconocidos(proyecto_tmp):
    e = proyecto_tmp / "entrada"
    _png(e / "P1_boca_B.png", modo="RGB")
    _png(e / "foto_cualquiera.png")
    inf = importar(e, proyecto_tmp, personaje="profesor")
    motivos = {r.archivo: r.motivo for r in inf.rechazados}
    assert "transparencia" in motivos["P1_boca_B.png"]
    assert "nomenclatura" in motivos["foto_cualquiera.png"]
    assert not inf.importados


def test_es_idempotente_y_no_borra_los_originales(proyecto_tmp):
    e = proyecto_tmp / "entrada"
    _png(e / "P1_boca_A.png", (32, 20))
    importar(e, proyecto_tmp, personaje="profesor")
    inf = importar(e, proyecto_tmp, personaje="profesor")
    assert (e / "P1_boca_A.png").is_file()
    assert len(inf.importados) == 1 and not inf.rechazados


def test_ignora_archivos_que_no_son_imagenes(proyecto_tmp):
    e = proyecto_tmp / "entrada"
    (e / "notas.txt").write_text("hola", encoding="utf-8")
    (e / ".gitkeep").write_text("", encoding="utf-8")
    inf = importar(e, proyecto_tmp, personaje="profesor")
    assert not inf.importados and not inf.rechazados
