"""El lote usa el pipeline nuevo (director, poses por vista, parpadeo) y elige el idioma de cada clase (FR-021, FR-101):
columna `idioma` en el manifiesto, reconocedor según el idioma, poses y escenario por clase."""
import csv
import sqlite3
from collections import Counter

import pytest

from src.errores import ErrorAccionable
from src.lote.cola import Cola, Trabajo
from src.lote.manifiesto import COLUMNAS, crear_manifiesto, encolar_manifiesto, leer_manifiesto
from src.lote.trabajadores import parametros_de


def _pose_v3(raiz, nombre, personaje="profesor"):
    carpeta = raiz / "personajes" / personaje / "poses" / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "config.yaml").write_text("version: 4\n", encoding="utf-8")


def _escenario(raiz, nombre):
    carpeta = raiz / "escenarios" / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "fondo.png").write_bytes(b"x")


def _csv(ruta, filas):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for fila in filas for k in fila}))
        w.writeheader()
        w.writerows(filas)
    return ruta


# ---------------- idioma en el manifiesto y la cola ----------------
def test_el_manifiesto_tiene_la_columna_idioma_y_por_defecto_es_espanol(proyecto_tmp):
    assert "idioma" in COLUMNAS
    (proyecto_tmp / "clases" / "c1.txt").write_text("hola", encoding="utf-8")
    (proyecto_tmp / "clases" / "c1.mp3").write_bytes(b"x")
    destino = proyecto_tmp / "lote" / "manifiestos" / "m.csv"
    crear_manifiesto(proyecto_tmp / "clases", "profesor", "L1", destino)
    assert leer_manifiesto(destino, proyecto_tmp)[0].idioma == "es"


def test_crear_manifiesto_puede_fijar_el_idioma_de_todas_las_clases(proyecto_tmp):
    (proyecto_tmp / "clases" / "c1.txt").write_text("hello", encoding="utf-8")
    (proyecto_tmp / "clases" / "c1.mp3").write_bytes(b"x")
    destino = proyecto_tmp / "m.csv"
    crear_manifiesto(proyecto_tmp / "clases", "profesor", "L1", destino, idioma="en")
    assert leer_manifiesto(destino, proyecto_tmp)[0].idioma == "en"


@pytest.mark.parametrize("valor, esperado", [("es", "es"), ("EN", "en"), ("mixto", "mixto"), ("", "es")])
def test_idiomas_validos_del_manifiesto(proyecto_tmp, valor, esperado):
    ruta = _csv(proyecto_tmp / "m.csv", [{"id": "c1", "audio": "", "guion": "g.txt", "idioma": valor}])
    (proyecto_tmp / "g.txt").write_text("hola", encoding="utf-8")
    ruta = _csv(proyecto_tmp / "m.csv", [{"id": "c1", "guion": str(proyecto_tmp / "g.txt"), "idioma": valor}])
    assert leer_manifiesto(ruta, proyecto_tmp)[0].idioma == esperado


def test_un_idioma_desconocido_se_rechaza_con_la_fila(proyecto_tmp):
    (proyecto_tmp / "g.txt").write_text("hola", encoding="utf-8")
    ruta = _csv(proyecto_tmp / "m.csv", [{"id": "c1", "guion": str(proyecto_tmp / "g.txt"), "idioma": "fr"}])
    with pytest.raises(ErrorAccionable) as exc:
        leer_manifiesto(ruta, proyecto_tmp)
    assert "fila 2" in str(exc.value) and "fr" in str(exc.value) and "es" in str(exc.value)


def test_la_cola_guarda_el_idioma_y_una_cola_antigua_se_actualiza_sola(proyecto_tmp):
    ruta = proyecto_tmp / "lote" / "cola.db"
    cola = Cola(ruta)
    cola.encolar([Trabajo(id="c1", idioma="en")])
    assert cola.reclamar().idioma == "en"
    antigua = proyecto_tmp / "lote" / "antigua.db"
    con = sqlite3.connect(antigua)
    con.execute("CREATE TABLE trabajos (orden INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, lote TEXT NOT NULL DEFAULT '', "
                "personaje TEXT NOT NULL DEFAULT 'profesor', audio TEXT, guion TEXT, poses TEXT NOT NULL DEFAULT '', "
                "escenarios TEXT NOT NULL DEFAULT '', resolucion TEXT NOT NULL DEFAULT '1280x720', semilla INTEGER, "
                "tts TEXT NOT NULL DEFAULT 'gemini-studio', genero TEXT, estado TEXT NOT NULL DEFAULT 'pendiente', "
                "intentos INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', salida TEXT NOT NULL DEFAULT '', "
                "inicio REAL NOT NULL DEFAULT 0, fin REAL NOT NULL DEFAULT 0, latido REAL NOT NULL DEFAULT 0)")
    con.execute("INSERT INTO trabajos (id) VALUES ('vieja')")
    con.commit()
    con.close()
    assert Cola(antigua).reclamar().idioma == "es"


# ---------------- parámetros de render de cada clase ----------------
@pytest.mark.parametrize("idioma, reconocedor", [("es", "phonetic"), ("en", "pocketSphinx"), ("mixto", "phonetic")])
def test_el_reconocedor_depende_del_idioma_de_la_clase(proyecto_tmp, idioma, reconocedor):
    p = parametros_de(Trabajo(id="c1", audio="a.mp3", idioma=idioma), proyecto_tmp)
    assert p.reconocedor == reconocedor


def test_con_poses_por_vista_el_lote_usa_todas_con_la_neutra_primero_y_el_director(proyecto_tmp):
    for n in ("frontal_explicar_01", "frontal_neutro_01", "tres_cuartos_der_neutro_01", "frontal_pulgar_01"):
        _pose_v3(proyecto_tmp, n)
    p = parametros_de(Trabajo(id="c1", audio="a.mp3"), proyecto_tmp)
    assert p.director is True and p.poses[0] == "frontal_neutro_01" and set(p.poses) == {
        "frontal_explicar_01", "frontal_neutro_01", "tres_cuartos_der_neutro_01", "frontal_pulgar_01"}
    assert p.pose is None


def test_la_columna_poses_restringe_las_poses_de_la_clase(proyecto_tmp):
    for n in ("frontal_explicar_01", "frontal_neutro_01", "frontal_pulgar_01"):
        _pose_v3(proyecto_tmp, n)
    p = parametros_de(Trabajo(id="c1", audio="a.mp3", poses="frontal_neutro_01; frontal_explicar_01"), proyecto_tmp)
    assert p.poses == ["frontal_neutro_01", "frontal_explicar_01"] and p.director is True


def test_poses_todas_equivale_a_dejarla_vacia(proyecto_tmp):
    for n in ("frontal_neutro_01", "frontal_pulgar_01"):
        _pose_v3(proyecto_tmp, n)
    a = parametros_de(Trabajo(id="c1", audio="a.mp3", poses="todas"), proyecto_tmp)
    b = parametros_de(Trabajo(id="c1", audio="a.mp3"), proyecto_tmp)
    assert a.poses == b.poses


def test_un_personaje_con_poses_antiguas_sigue_como_antes(proyecto_tmp):
    carpeta = proyecto_tmp / "personajes" / "profesor" / "poses" / "P1_profesor"
    carpeta.mkdir(parents=True)
    p = parametros_de(Trabajo(id="c1", audio="a.mp3", poses="P1"), proyecto_tmp)
    assert p.pose == "P1" and p.poses is None and p.director is False


def test_una_pose_inexistente_en_la_columna_se_avisa_al_renderizar_con_las_disponibles(proyecto_tmp):
    _pose_v3(proyecto_tmp, "frontal_neutro_01")
    p = parametros_de(Trabajo(id="c1", audio="a.mp3", poses="frontal_no_existe_09"), proyecto_tmp)
    assert p.poses == ["frontal_no_existe_09"]                       # render la rechaza listando las disponibles (NFR-006)


# ---------------- escenario por clase ----------------
def test_sin_escenarios_indicados_las_clases_se_reparten_entre_todos_los_escenarios(proyecto_tmp):
    for e in ("E1_salon", "E2_calle", "E3_lab"):
        _escenario(proyecto_tmp, e)
    elegidos = Counter(parametros_de(Trabajo(id=f"clase_{i:04d}", audio="a.mp3"), proyecto_tmp).escenario for i in range(300))
    assert set(elegidos) == {"E1", "E2", "E3"} and min(elegidos.values()) > 60


def test_el_escenario_de_una_clase_es_siempre_el_mismo_para_el_mismo_id(proyecto_tmp):
    for e in ("E1_salon", "E2_calle"):
        _escenario(proyecto_tmp, e)
    elegir = lambda: parametros_de(Trabajo(id="clase_0007", audio="a.mp3"), proyecto_tmp).escenario
    assert elegir() == elegir()


def test_la_columna_escenarios_limita_la_eleccion(proyecto_tmp):
    for e in ("E1_salon", "E2_calle", "E3_lab"):
        _escenario(proyecto_tmp, e)
    elegidos = {parametros_de(Trabajo(id=f"c{i}", audio="a.mp3", escenarios="E2;E3"), proyecto_tmp).escenario for i in range(80)}
    assert elegidos == {"E2", "E3"}


def test_sin_carpeta_de_escenarios_no_falla(proyecto_tmp):
    import shutil
    shutil.rmtree(proyecto_tmp / "escenarios")
    assert parametros_de(Trabajo(id="c1", audio="a.mp3"), proyecto_tmp).escenario is None


def test_el_manifiesto_completo_llega_hasta_los_parametros_de_render(proyecto_tmp):
    from src.lote.cola import Cola
    _pose_v3(proyecto_tmp, "frontal_neutro_01")
    (proyecto_tmp / "clases" / "c1.txt").write_text("hello", encoding="utf-8")
    (proyecto_tmp / "clases" / "c1.mp3").write_bytes(b"x")
    destino = proyecto_tmp / "m.csv"
    crear_manifiesto(proyecto_tmp / "clases", "profesor", "L1", destino, idioma="en")
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    encolar_manifiesto(cola, destino, proyecto_tmp)
    p = parametros_de(cola.reclamar(), proyecto_tmp)
    assert p.reconocedor == "pocketSphinx" and p.director is True and p.poses == ["frontal_neutro_01"]
