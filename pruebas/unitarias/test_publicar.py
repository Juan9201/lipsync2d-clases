"""Subtitular y publicar: las clases renderizadas y las humanas de la carpeta de entrada acaban subtituladas en Drive, por nivel y módulo."""
import sqlite3

import pytest
import yaml

from src import publicar
from src.errores import ErrorAccionable


def _raiz(tmp_path, drive=True):
    raiz = tmp_path / "proy"
    (raiz / "salidas").mkdir(parents=True)
    (raiz / "lote").mkdir()
    if drive:
        (tmp_path / "gd").mkdir()
    (raiz / "publicacion.yaml").write_text(yaml.safe_dump({"drive": str(tmp_path / "gd" / "Clases renderizadas"),
                                                           "entrada_humano": str(tmp_path / "gd" / "humano" / "entrada")}), encoding="utf-8")
    return raiz


def _cola(raiz, filas):
    c = sqlite3.connect(raiz / "lote" / "cola.db")
    c.execute("CREATE TABLE trabajos (orden INTEGER PRIMARY KEY, id TEXT, estado TEXT, salida TEXT)")
    c.executemany("INSERT INTO trabajos(id, estado, salida) VALUES (?,?,?)", filas)
    c.commit(); c.close()


def _falso(llamadas=None, falla=None):
    def f(video, destino, nombre, raiz, aviso=None):
        if llamadas is not None:
            llamadas.append(nombre)
        if falla:
            raise ErrorAccionable(falla, "reintenta")
        destino.mkdir(parents=True, exist_ok=True)
        (destino / f"{nombre}_subtitulado.mp4").write_bytes(b"video" * 10)
        (destino / f"{nombre}_subtitulos.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhola\n", encoding="utf-8")
        return {"video": destino / f"{nombre}_subtitulado.mp4", "srt": destino / f"{nombre}_subtitulos.srt"}
    return f


@pytest.mark.parametrize("id_clase,nivel,modulo", [("A1-M05-3", "A1", "M05"), ("B2-M40-1", "B2", "M40")])
def test_la_carpeta_de_drive_es_nivel_y_modulo(id_clase, nivel, modulo):
    assert publicar.carpeta_drive({"drive": "D:/Drive/Clases"}, id_clase).as_posix() == f"D:/Drive/Clases/{nivel}/{modulo}"


def test_un_nombre_que_no_es_una_clase_se_rechaza():
    with pytest.raises(ErrorAccionable):
        publicar.partes_de_id("video_final")


def test_una_clase_renderizada_se_subtitula_y_se_publica_en_su_modulo(tmp_path):
    raiz = _raiz(tmp_path)
    video = raiz / "salidas" / "A1-M05-3_20261026.mp4"; video.write_bytes(b"x" * 100)
    prueba = raiz / "salidas" / "prueba_A1-M05-3_60-100s_20261026.mp4"; prueba.write_bytes(b"x")
    _cola(raiz, [("A1-M05-3", "hecho", str(video)), ("A1-M05-4", "pendiente", ""), ("A1-M06-2", "hecho", str(prueba))])
    llamadas = []
    r = publicar.correr(raiz, una_vez=True, subtitular=_falso(llamadas))
    assert r == {"publicadas": 1, "con_error": 0} and llamadas == ["A1-M05-3"]      # la de prueba y la pendiente no cuentan
    destino = tmp_path / "gd" / "Clases renderizadas" / "A1" / "M05"
    assert (destino / "A1-M05-3_subtitulado.mp4").is_file() and (destino / "A1-M05-3_subtitulos.srt").is_file()
    assert (raiz / "salidas" / "subtitulados" / "A1-M05-3_subtitulado.mp4").is_file()             # se conserva la copia local
    assert [f["estado"] for f in publicar.Registro(raiz / "lote" / "publicacion.db").todas()] == ["publicado"]


def test_no_se_subtitula_dos_veces_la_misma_clase(tmp_path):
    raiz = _raiz(tmp_path)
    video = raiz / "salidas" / "A1-M05-3_20261026.mp4"; video.write_bytes(b"x")
    _cola(raiz, [("A1-M05-3", "hecho", str(video))])
    publicar.correr(raiz, una_vez=True, subtitular=_falso())
    llamadas = []
    publicar.correr(raiz, una_vez=True, subtitular=_falso(llamadas))
    assert llamadas == []


def test_un_video_humano_de_la_entrada_se_procesa_y_el_original_pasa_a_procesadas(tmp_path):
    raiz = _raiz(tmp_path)
    entrada = tmp_path / "gd" / "humano" / "entrada"; entrada.mkdir(parents=True)
    (entrada / "A2-M07-1 grabacion final.mp4").write_bytes(b"x" * 50)
    (entrada / "notas.txt").write_text("no es video")
    (entrada / "video_sin_id.mp4").write_bytes(b"x")
    llamadas = []
    assert publicar.correr(raiz, una_vez=True, subtitular=_falso(llamadas))["publicadas"] == 1
    assert llamadas == ["A2-M07-1"]
    assert (tmp_path / "gd" / "Clases renderizadas" / "A2" / "M07" / "A2-M07-1_subtitulado.mp4").is_file()
    assert (tmp_path / "gd" / "humano" / "procesadas" / "A2-M07-1 grabacion final.mp4").is_file()
    assert sorted(p.name for p in entrada.iterdir()) == ["notas.txt", "video_sin_id.mp4"]


def test_si_falla_la_herramienta_la_clase_queda_en_error_y_las_demas_siguen(tmp_path):
    raiz = _raiz(tmp_path)
    for n in (2, 3):
        (raiz / "salidas" / f"A1-M05-{n}_20261026.mp4").write_bytes(b"x")
    _cola(raiz, [(f"A1-M05-{n}", "hecho", str(raiz / "salidas" / f"A1-M05-{n}_20261026.mp4")) for n in (2, 3)])
    def mitad(video, destino, nombre, raiz, aviso=None):
        if nombre == "A1-M05-2":
            raise ErrorAccionable("La herramienta de subtítulos falló", "x")
        return _falso()(video, destino, nombre, raiz)
    assert publicar.correr(raiz, una_vez=True, subtitular=mitad) == {"publicadas": 1, "con_error": 1}
    reg = publicar.Registro(raiz / "lote" / "publicacion.db")
    assert {f["id"]: f["estado"] for f in reg.todas()} == {"A1-M05-2": "error", "A1-M05-3": "publicado"}
    assert reg.reintentar() == 1
    assert publicar.correr(raiz, una_vez=True, subtitular=_falso())["publicadas"] == 1


def test_si_drive_no_esta_la_clase_queda_subtitulada_y_se_publica_despues(tmp_path):
    raiz = _raiz(tmp_path, drive=False)
    video = raiz / "salidas" / "A1-M05-3_20261026.mp4"; video.write_bytes(b"x")
    _cola(raiz, [("A1-M05-3", "hecho", str(video))])
    cfg = publicar.cargar_config(raiz)
    reg = publicar.Registro(raiz / "lote" / "publicacion.db")
    publicar.descubrir(raiz, reg, cfg)
    assert publicar.procesar_una(raiz, reg, cfg, _falso()) == "A1-M05-3"
    assert reg.todas()[0]["estado"] == "subtitulado" and "Drive" in reg.todas()[0]["error"]
    (tmp_path / "gd").mkdir()
    llamadas = []
    publicar.procesar_una(raiz, reg, cfg, _falso(llamadas))
    assert reg.todas()[0]["estado"] == "publicado" and llamadas == []                         # no se vuelve a subtitular
