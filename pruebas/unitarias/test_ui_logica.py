"""T083 (FR-064, FR-071): la lógica de la interfaz — guiones, voces, render y lote — sin navegador."""
import csv
import sys

import pytest
import yaml

from src.errores import ErrorAccionable
from src.ui import logica
from src.ui.logica import Tareas


# ---------------- guiones ----------------
def test_guardar_una_clase_crea_el_guion_con_sus_ajustes_y_el_siguiente_numero(proyecto_tmp):
    a = logica.guardar_clase(proyecto_tmp, "Hola a todos. Hoy aprendemos.", idioma="en", genero="mujer")
    b = logica.guardar_clase(proyecto_tmp, "Segunda clase.")
    assert (a["id"], b["id"]) == ("clase_0001", "clase_0002")
    assert a["idioma"] == "en" and a["genero"] == "mujer" and a["palabras"] == 5
    assert (proyecto_tmp / "clases" / "clase_0001.txt").read_text(encoding="utf-8").startswith("Hola a todos")
    assert b["idioma"] == "es" and b["genero"] == "hombre"                       # por defecto


def test_un_guion_vacio_o_un_id_malo_se_rechazan_con_una_accion(proyecto_tmp):
    with pytest.raises(ErrorAccionable) as e1:
        logica.guardar_clase(proyecto_tmp, "   ")
    assert "vacío" in str(e1.value)
    for malo in ("../fuera", "a b", "x/y", "ñ" * 3, "a" * 80):
        with pytest.raises(ErrorAccionable):
            logica.guardar_clase(proyecto_tmp, "texto", malo)


def test_idioma_y_genero_invalidos_se_rechazan(proyecto_tmp):
    with pytest.raises(ErrorAccionable):
        logica.guardar_clase(proyecto_tmp, "texto", idioma="fr")
    with pytest.raises(ErrorAccionable):
        logica.guardar_clase(proyecto_tmp, "texto", genero="otro")


def test_importar_varios_archivos_usa_el_nombre_del_archivo_y_no_pisa_los_existentes(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "ya existía", "leccion_1")
    ids = logica.importar_guiones(proyecto_tmp, [{"nombre": "leccion 1.txt", "texto": "uno"}, {"nombre": "leccion_1.txt", "texto": "dos"},
                                                 {"nombre": "Tema ñandú.txt", "texto": "tres"}], idioma="es")
    assert ids == ["leccion_1_2", "leccion_1_3", "Tema_and"]
    assert (proyecto_tmp / "clases" / "leccion_1.txt").read_text(encoding="utf-8").startswith("ya existía")


def test_actualizar_cambia_ajustes_y_texto_y_conserva_lo_demas(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "texto viejo", "c1", idioma="en", genero="mujer", escenarios="E2")
    ficha = logica.actualizar_clase(proyecto_tmp, "c1", genero="hombre", texto="texto nuevo")
    assert ficha["genero"] == "hombre" and ficha["idioma"] == "en" and ficha["escenarios"] == "E2"
    assert logica.leer_texto(proyecto_tmp, "c1").strip() == "texto nuevo"
    with pytest.raises(ErrorAccionable):
        logica.actualizar_clase(proyecto_tmp, "no_existe", genero="mujer")


def test_quitar_una_clase_no_borra_el_guion_lo_mueve_a_la_papelera(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "texto", "c1")
    logica.eliminar_clase(proyecto_tmp, "c1")
    assert logica.listar_clases(proyecto_tmp) == []
    assert len(list((proyecto_tmp / "clases" / "_papelera").glob("c1-*.txt"))) == 1


def test_la_lista_dice_si_hay_voz_y_video(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "uno dos tres", "c1")
    assert logica.listar_clases(proyecto_tmp)[0]["audio"] is None
    (proyecto_tmp / "clases" / "c1.mp3").write_bytes(b"x")
    (proyecto_tmp / "salidas" / "c1_20261016.mp4").write_bytes(b"x")
    (proyecto_tmp / "salidas" / "c1_20261017.part.mp4").write_bytes(b"x")
    ficha = logica.listar_clases(proyecto_tmp)[0]
    assert ficha["audio"] == "c1.mp3" and ficha["video"] == "c1_20261016.mp4"


# ---------------- recursos ----------------
def test_escenarios_y_poses_disponibles(proyecto_tmp):
    for e in ("E2_calle", "E10_lab", "E1_salon"):
        (proyecto_tmp / "escenarios" / e).mkdir()
    (proyecto_tmp / "escenarios" / "E2_calle" / "fondo.mp4").write_bytes(b"x")
    assert [(e["id"], e["tipo"]) for e in logica.escenarios_disponibles(proyecto_tmp)] == [("E1", "imagen"), ("E2", "video"), ("E10", "imagen")]
    base = proyecto_tmp / "personajes" / "profesor" / "poses"
    (base / "frontal_neutro_01").mkdir(parents=True)
    (base / "frontal_neutro_01" / "parpadeo_cerrado.png").write_bytes(b"x")
    (base / "P1_viejo").mkdir()
    poses = logica.poses_disponibles(proyecto_tmp)
    assert [(p["id"], p["parpadeo"]) for p in poses] == [("frontal_neutro_01", True)]


# ---------------- voces ----------------
def test_guardar_voces_va_a_tts_usuario_y_no_toca_tts_yaml(proyecto_tmp):
    original = "gemini-studio:\n  voces: {hombre: es-original-h, mujer: es-original-m}  # comentario\n"
    (proyecto_tmp / "tts.yaml").write_text(original, encoding="utf-8")
    logica.guardar_voces(proyecto_tmp, "en", "en-h", None)
    logica.guardar_voces(proyecto_tmp, "es", None, "es-nueva-m")
    assert (proyecto_tmp / "tts.yaml").read_text(encoding="utf-8") == original
    v = logica.voces_guardadas(proyecto_tmp)
    assert v["en"] == {"hombre": "en-h", "mujer": None} and v["es"] == {"hombre": "es-original-h", "mujer": "es-nueva-m"}


def test_las_voces_elegidas_las_usa_el_proveedor_de_tts(proyecto_tmp):
    from src.tts import obtener_proveedor
    (proyecto_tmp / "tts.yaml").write_text("gemini-studio: {idioma: es-419, voces: {hombre: x, mujer: y}}\n", encoding="utf-8")
    logica.guardar_voces(proyecto_tmp, "en", "en-voz-h", "en-voz-m")
    _, op = obtener_proveedor("gemini-studio", proyecto_tmp, "mujer", "en")
    assert op.voz == "en-voz-m" and op.idioma == "en-US"


def test_guardar_voces_sin_elegir_ninguna_o_con_idioma_raro_falla(proyecto_tmp):
    with pytest.raises(ErrorAccionable):
        logica.guardar_voces(proyecto_tmp, "es", None, None)
    with pytest.raises(ErrorAccionable):
        logica.guardar_voces(proyecto_tmp, "fr", "a", "b")


# ---------------- render ----------------
def test_el_comando_de_render_lleva_idioma_poses_y_director(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "hello", "c1", idioma="en", poses="frontal_neutro_01; frontal_explicar_01", escenarios="E2")
    (proyecto_tmp / "clases" / "c1.mp3").write_bytes(b"x")
    cmd = logica.comando_render(proyecto_tmp, "c1", plano="PL4")
    assert cmd[:3] == [sys.executable, "-m", "src.render"]
    assert cmd[cmd.index("--idioma") + 1] == "en" and cmd[cmd.index("--escenario") + 1] == "E2"
    assert cmd[cmd.index("--poses") + 1] == "frontal_neutro_01,frontal_explicar_01"
    assert "--director" in cmd and cmd[cmd.index("--plano") + 1] == "PL4"
    assert "--no-director" in logica.comando_render(proyecto_tmp, "c1", director=False)


def test_sin_voz_no_se_puede_renderizar_y_dice_que_hacer(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "hola", "c1")
    with pytest.raises(ErrorAccionable) as exc:
        logica.comando_render(proyecto_tmp, "c1")
    assert "Generar voz" in str(exc.value)


# ---------------- tareas ----------------
def _esperar(tareas, tid, segundos=15):
    import time
    fin = time.time() + segundos
    while time.time() < fin:
        t = next(x for x in tareas.listar() if x["id"] == tid)
        if t["estado"] != "en curso":
            return t
        time.sleep(0.05)
    raise AssertionError("la tarea no terminó")


def test_una_tarea_de_funcion_guarda_su_resultado_o_su_error_legible(proyecto_tmp):
    tareas = Tareas(proyecto_tmp)
    ok = _esperar(tareas, tareas.lanzar_funcion("voz", lambda: proyecto_tmp / "clases" / "a.mp3"))
    assert ok["estado"] == "hecha" and ok["salida"].endswith("a.mp3")

    def falla():
        raise ErrorAccionable("La webapp no responde", "Enciéndela")
    mal = _esperar(tareas, tareas.lanzar_funcion("voz", falla))
    assert mal["estado"] == "error" and "La webapp no responde" in mal["error"]
    raro = _esperar(tareas, tareas.lanzar_funcion("voz", lambda: 1 / 0))
    assert raro["estado"] == "error" and "ZeroDivisionError" in raro["error"]


def test_una_tarea_de_comando_guarda_el_log_y_la_salida(proyecto_tmp):
    tareas = Tareas(proyecto_tmp)
    cmd = [sys.executable, "-c", "print('trabajando'); print('Video listo: C:\\\\x\\\\clase_20261016.mp4')"]
    t = _esperar(tareas, tareas.lanzar_comando("render", cmd, "c1", logica.salida_de_render))
    assert t["estado"] == "hecha" and t["salida"] == "clase_20261016.mp4" and "trabajando" in t["log"]


def test_un_comando_que_falla_muestra_la_linea_de_error(proyecto_tmp):
    tareas = Tareas(proyecto_tmp)
    cmd = [sys.executable, "-c", "import sys; print('ERROR: falta el audio'); sys.exit(1)"]
    t = _esperar(tareas, tareas.lanzar_comando("render", cmd))
    assert t["estado"] == "error" and "falta el audio" in t["error"]


# ---------------- lote ----------------
def test_crear_lote_escribe_el_manifiesto_con_idioma_y_genero_y_encola(proyecto_tmp):
    logica.guardar_clase(proyecto_tmp, "hola", "c1", idioma="es", genero="mujer")
    logica.guardar_clase(proyecto_tmp, "hello", "c2", idioma="en")
    r = logica.crear_lote(proyecto_tmp, "L1", ["c1", "c2"])
    assert r["encoladas"] == 2
    filas = list(csv.DictReader(open(proyecto_tmp / "lote" / "manifiestos" / "L1.csv", encoding="utf-8-sig")))
    assert {(f["id"], f["idioma"], f["genero"]) for f in filas} == {("c1", "es", "mujer"), ("c2", "en", "hombre")}
    assert logica.crear_lote(proyecto_tmp, "L1", ["c1"])["ya_estaban"] == 1
    estado = logica.estado_lote(proyecto_tmp)
    assert estado["total"] == 2 and estado["estados"] == {"pendiente": 2}


def test_crear_lote_valida_el_nombre_y_que_haya_clases(proyecto_tmp):
    with pytest.raises(ErrorAccionable):
        logica.crear_lote(proyecto_tmp, "L1", [])
    logica.guardar_clase(proyecto_tmp, "hola", "c1")
    with pytest.raises(ErrorAccionable):
        logica.crear_lote(proyecto_tmp, "../mal", ["c1"])


def test_el_estado_del_lote_sin_cola_es_vacio(proyecto_tmp):
    assert logica.estado_lote(proyecto_tmp) == {"total": 0, "estados": {}, "trabajos": []}


def test_render_y_lote_de_una_clase_inexistente_dan_un_error_claro_no_un_fallo(proyecto_tmp):
    with pytest.raises(ErrorAccionable) as e1:
        logica.comando_render(proyecto_tmp, "no_existe")
    assert "No existe la clase" in str(e1.value)
    with pytest.raises(ErrorAccionable):
        logica.crear_lote(proyecto_tmp, "L1", ["no_existe"])


def test_escuchar_una_voz_elegida_genera_la_muestra_con_esa_voz(proyecto_tmp, monkeypatch):
    """Regresión: elegir una voz del catálogo y pulsar «Escuchar» fallaba con FrozenInstanceError."""
    from src.tts.base import OpcionesTTS
    usadas = []

    def falso_sintetizar(proveedor, texto, destino, opciones):
        usadas.append((opciones.voz, texto))
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"mp3")
        return destino
    monkeypatch.setattr("src.tts.obtener_proveedor", lambda nombre, raiz=None, genero=None, idioma=None: (object(), OpcionesTTS(voz="es-original")))
    monkeypatch.setattr("src.tts.comun.sintetizar_texto", falso_sintetizar)
    ruta = logica.muestra_de_voz(proyecto_tmp, "es", "hombre", "es-419-podcaster-8")
    assert ruta.is_file() and ruta.name == "es_hombre_es-419-podcaster-8.mp3"
    assert usadas == [("es-419-podcaster-8", logica.TEXTO_MUESTRA["es"])]
    logica.muestra_de_voz(proyecto_tmp, "es", "hombre", "es-419-podcaster-8")
    assert len(usadas) == 1                                          # la muestra ya existe: no se vuelve a generar
    logica.muestra_de_voz(proyecto_tmp, "en", "mujer")
    assert usadas[-1][0] == "es-original"                            # sin voz elegida usa la guardada
