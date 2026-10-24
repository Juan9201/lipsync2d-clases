"""El servidor de la interfaz: rutas, seguridad (Host, cabecera X-Lipsync, rutas fuera de carpeta) y entrega de video con Range."""
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from src.ui.servidor import crear_servidor


@pytest.fixture
def srv(proyecto_tmp):
    servidor = crear_servidor(proyecto_tmp, 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield proyecto_tmp, f"http://127.0.0.1:{servidor.server_address[1]}", servidor
    servidor.shutdown()
    servidor.server_close()


def _pedir(url, ruta, cuerpo=None, cabeceras=None, metodo=None):
    h = dict(cabeceras or {})
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url + ruta, data=datos, headers=h, method=metodo or ("POST" if cuerpo is not None else "GET"))
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _post(url, ruta, cuerpo):
    codigo, datos, _ = _pedir(url, ruta, cuerpo, {"X-Lipsync": "1"})
    return codigo, json.loads(datos)


# ---------------- páginas ----------------
def test_la_pagina_principal_y_sus_archivos_se_sirven(srv):
    _, url, _ = srv
    for ruta, tipo in (("/", "text/html"), ("/app.js", "text/javascript"), ("/app.css", "text/css")):
        codigo, cuerpo, cab = _pedir(url, ruta)
        assert codigo == 200 and cab["Content-Type"].startswith(tipo) and len(cuerpo) > 100


def test_crear_listar_editar_y_quitar_clases_por_http(srv):
    raiz, url, _ = srv
    codigo, c = _post(url, "/api/clases", {"texto": "Hola mundo", "idioma": "en", "genero": "mujer"})
    assert codigo == 200 and c["id"] == "clase_0001" and c["idioma"] == "en"
    _, datos, _ = _pedir(url, "/api/clases")
    d = json.loads(datos)
    assert [x["id"] for x in d["clases"]] == ["clase_0001"] and d["siguiente_id"] == "clase_0002"
    assert json.loads(_pedir(url, "/api/clases/clase_0001/texto")[1])["texto"].startswith("Hola mundo")
    assert _post(url, "/api/clases/clase_0001", {"genero": "hombre", "texto": "Otro texto"})[1]["genero"] == "hombre"
    assert _post(url, "/api/clases/importar", {"archivos": [{"nombre": "a.txt", "texto": "uno"}]})[1]["ids"] == ["a"]
    assert _post(url, "/api/clases/clase_0001/eliminar", {})[1] == {"ok": True}
    assert [x["id"] for x in json.loads(_pedir(url, "/api/clases")[1])["clases"]] == ["a"]


def test_los_errores_llegan_en_espanol_con_la_accion(srv):
    _, url, _ = srv
    codigo, d = _post(url, "/api/clases", {"texto": "  "})
    assert codigo == 400 and "vacío" in d["error"] and "Pega" in d["error"]
    codigo, d = _post(url, "/api/render", {"id": "no_existe"})
    assert codigo == 400 and "error" in d
    assert _post(url, "/api/no_existe", {})[0] == 404


def test_el_estado_del_proyecto_responde_sin_necesitar_la_voz(srv):
    _, url, _ = srv
    d = json.loads(_pedir(url, "/api/estado")[1])
    assert {"ffmpeg", "rhubarb", "tts", "poses", "escenarios"} <= set(d)


def test_el_lote_por_http(srv):
    raiz, url, _ = srv
    _post(url, "/api/clases", {"texto": "hola", "id": "c1"})
    assert _post(url, "/api/lote", {"nombre": "L1", "ids": ["c1"]})[1]["encoladas"] == 1
    d = json.loads(_pedir(url, "/api/lote")[1])
    assert d["total"] == 1 and d["trabajos"][0]["id"] == "c1"


# ---------------- seguridad ----------------
def test_una_peticion_que_modifica_sin_la_cabecera_de_seguridad_se_rechaza(srv):
    _, url, _ = srv
    codigo, _, _ = _pedir(url, "/api/clases", {"texto": "hola"})
    assert codigo == 403


def test_un_host_ajeno_se_rechaza(srv):
    _, url, _ = srv
    for ruta in ("/", "/api/clases"):
        codigo, _, _ = _pedir(url, ruta, cabeceras={"Host": "malo.example.com"})
        assert codigo == 403
    codigo, _, _ = _pedir(url, "/api/clases", {"texto": "hola"}, {"Host": "malo.example.com", "X-Lipsync": "1"})
    assert codigo == 403


@pytest.mark.parametrize("ruta", ["/salidas/..%2F..%2Ftts.yaml", "/salidas/../tts.yaml", "/salidas/a.exe", "/muestras/..%5Cx.mp3",
                                  "/salidas/%2e%2e/x.mp4"])
def test_no_se_pueden_pedir_archivos_fuera_de_salidas_y_muestras(srv, ruta):
    raiz, url, _ = srv
    (raiz / "tts.yaml").write_text("secreto: 1\n", encoding="utf-8")
    codigo, cuerpo, _ = _pedir(url, ruta)
    assert codigo in (400, 404) and b"secreto" not in cuerpo


# ---------------- video con Range ----------------
def test_el_video_se_entrega_completo_y_por_tramos(srv):
    raiz, url, _ = srv
    datos = bytes(range(256)) * 40
    (raiz / "salidas" / "c1_20261016.mp4").write_bytes(datos)
    codigo, cuerpo, cab = _pedir(url, "/salidas/c1_20261016.mp4")
    assert codigo == 200 and cuerpo == datos and cab["Accept-Ranges"] == "bytes"
    codigo, cuerpo, cab = _pedir(url, "/salidas/c1_20261016.mp4", cabeceras={"Range": "bytes=100-199"})
    assert codigo == 206 and cuerpo == datos[100:200] and cab["Content-Range"] == f"bytes 100-199/{len(datos)}"
    codigo, cuerpo, _ = _pedir(url, "/salidas/c1_20261016.mp4", cabeceras={"Range": "bytes=-50"})
    assert codigo == 206 and cuerpo == datos[-50:]
    codigo, _, _ = _pedir(url, "/salidas/c1_20261016.mp4", cabeceras={"Range": f"bytes={len(datos) + 10}-"})
    assert codigo == 416


def test_un_video_que_no_existe_da_404(srv):
    _, url, _ = srv
    assert _pedir(url, "/salidas/no_hay.mp4")[0] == 404


def test_importar_una_carpeta_de_guiones_por_http(srv, tmp_path):
    raiz, url, _ = srv
    drive = tmp_path / "Guiones" / "A1"
    drive.mkdir(parents=True)
    texto = "\n\n".join(" ".join(f"p{i}w{k}" for k in range(120)) + "." for i in range(6))
    (drive / "A1-M01-2 IA - Alphabet - Vowels.txt").write_text(texto, encoding="utf-8")
    (drive / "A1-M01-1 HUMANO - Alphabet - Letters.txt").write_text(texto, encoding="utf-8")
    codigo, r = _post(url, "/api/clases/importar-carpeta", {"carpeta": str(tmp_path / "Guiones")})
    assert codigo == 200 and r["creadas"] == ["A1-M01-2"] and r["omitidas_humano"] == ["A1-M01-1"]
    codigo, r = _post(url, "/api/clases/importar-carpeta", {"carpeta": str(tmp_path / "no_existe")})
    assert codigo == 400 and "carpeta" in r["error"].lower()


def test_abrir_la_carpeta_de_videos_usa_el_explorador_sin_abrir_nada_de_verdad(srv, monkeypatch):
    from src.ui import logica
    raiz, url, _ = srv
    abiertas = []
    monkeypatch.setattr(logica, "_abrir_en_explorador", abiertas.append)
    codigo, r = _post(url, "/api/salidas/abrir", {})
    assert codigo == 200 and r["carpeta"].endswith("salidas") and abiertas == [raiz / "salidas"]


def test_progreso_en_vivo_devuelve_las_etapas_con_la_hora_del_servidor(srv):
    from src.progreso import SeguimientoClase
    raiz, url, _ = srv
    s = SeguimientoClase(raiz, "A1-M01-2")
    s.empezar("rhubarb")
    time.sleep(0.25)                                            # el avance se limita a cinco escrituras por segundo
    s.avance(30, 120)
    codigo, cuerpo, _ = _pedir(url, "/api/progreso")
    d = json.loads(cuerpo)
    assert codigo == 200 and abs(d["ahora_ms"] - s.inicio_ms) < 60_000
    c = d["clases"][0]
    assert (c["clase"], c["estado"], c["actual"], c["fraccion"]) == ("A1-M01-2", "en_curso", "rhubarb", 0.25)


# ---------------- producir (un solo clic: escenario + lote + arranque) ----------------
@pytest.fixture
def produccion(srv, monkeypatch):
    from src.ui import logica
    raiz, url, _ = srv
    for i in (1, 2, 3):
        _post(url, "/api/clases", {"texto": "Hola " * 200, "id": f"A1-M01-{i}", "idioma": "mixto"})
    carpeta = raiz / "escenarios" / "E2_calle"
    carpeta.mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (1280, 720), (10, 80, 120)).save(carpeta / "fondo.png")
    lanzados = []
    monkeypatch.setattr(logica.Tareas, "lanzar_comando", lambda self, titulo, cmd, clase="", buscar_salida=None: lanzados.append((titulo, cmd)) or "t1")
    return raiz, url, lanzados


def test_producir_asigna_el_escenario_arma_el_lote_y_arranca_los_trabajadores(produccion):
    import json as _json
    raiz, url, lanzados = produccion
    codigo, r = _post(url, "/api/producir", {"ids": ["A1-M01-1", "A1-M01-2"], "escenario": "E2", "trabajadores": 2})
    assert codigo == 200 and r["encoladas"] == 2 and r["ya_estaban"] == 0 and r["lote"].startswith("prod-")
    assert _json.loads((raiz / "clases" / "A1-M01-1.json").read_text(encoding="utf-8"))["escenarios"] == "E2"
    assert _json.loads((raiz / "clases" / "A1-M01-3.json").read_text(encoding="utf-8"))["escenarios"] == ""     # las no marcadas no se tocan
    assert len(lanzados) == 1 and lanzados[0][1][-3:] == ["correr", "--trabajadores", "2"]


def test_producir_sin_escenario_deja_el_automatico_y_repetir_no_duplica(produccion):
    raiz, url, lanzados = produccion
    assert _post(url, "/api/producir", {"ids": ["A1-M01-1"], "escenario": ""})[0] == 200
    lanzados.clear()
    codigo, r = _post(url, "/api/producir", {"ids": ["A1-M01-1", "A1-M01-3"], "escenario": ""})
    assert codigo == 200 and r["encoladas"] == 1 and r["ya_estaban"] == 1 and len(lanzados) == 1


def test_producir_rechaza_pedidos_incorrectos_sin_lanzar_nada(produccion):
    raiz, url, lanzados = produccion
    assert _post(url, "/api/producir", {"ids": []})[0] == 400
    codigo, r = _post(url, "/api/producir", {"ids": ["A1-M01-1"], "escenario": "E9"})
    assert codigo == 400 and "E9" in r["error"]
    assert _post(url, "/api/producir", {"ids": ["no-existe"]})[0] == 400
    assert _post(url, "/api/producir", {"ids": ["A1-M01-1"], "trabajadores": 99})[0] == 200               # se limita a 1–4, no falla
    assert lanzados[-1][1][-1] == "4"
    assert len(lanzados) == 1


def test_producir_no_arranca_otro_lote_si_ya_hay_uno_corriendo(produccion, monkeypatch):
    from src.ui import logica
    raiz, url, lanzados = produccion
    monkeypatch.setattr(logica.Tareas, "listar", lambda self: [{"titulo": "Lote con 2 trabajadores", "estado": "en curso"}])
    codigo, r = _post(url, "/api/producir", {"ids": ["A1-M01-1"]})
    assert codigo == 400 and "ya hay un lote" in r["error"].lower() and lanzados == []
