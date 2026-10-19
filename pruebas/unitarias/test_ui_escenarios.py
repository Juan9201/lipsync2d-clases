"""Escenarios (fondos) desde la interfaz: subir, validar, numerar, reemplazar, quitar y miniaturas — lógica y HTTP."""
import io
import json
import subprocess
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest
from PIL import Image

from src import rutas
from src.errores import ErrorAccionable
from src.ui import logica
from src.ui.servidor import crear_servidor


def _png(ruta, tam=(1920, 1080), color=(40, 90, 160)):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", tam, color).save(ruta)
    return ruta


# ---------------- lógica ----------------
def test_agregar_un_fondo_de_imagen_lo_numera_y_lo_deja_listo_para_usar(proyecto_tmp):
    e = logica.agregar_escenario(proyecto_tmp, "Salón de clase", ".png", _png(proyecto_tmp / "t" / "a.png"))
    assert e["id"] == "E1" and e["tipo"] == "imagen" and (e["ancho"], e["alto"]) == (1920, 1080)
    assert e["carpeta"].startswith("E1_") and ".." not in e["carpeta"]
    assert (proyecto_tmp / "escenarios" / e["carpeta"] / "fondo.png").is_file()
    e2 = logica.agregar_escenario(proyecto_tmp, "calle", ".jpg", _png(proyecto_tmp / "t" / "b.jpg"))
    assert e2["id"] == "E2"
    assert [x["id"] for x in logica.escenarios_disponibles(proyecto_tmp)] == ["E1", "E2"]


def test_el_numero_continua_tras_el_mayor_existente(proyecto_tmp):
    (proyecto_tmp / "escenarios" / "E7_viejo").mkdir(parents=True)
    assert logica.agregar_escenario(proyecto_tmp, "nuevo", ".png", _png(proyecto_tmp / "t" / "a.png"))["id"] == "E8"


def test_un_fondo_que_no_es_16_9_se_rechaza_y_no_deja_nada(proyecto_tmp):
    with pytest.raises(ErrorAccionable) as exc:
        logica.agregar_escenario(proyecto_tmp, "cuadrado", ".png", _png(proyecto_tmp / "t" / "c.png", (1000, 1000)))
    assert "16:9" in str(exc.value)
    assert logica.escenarios_disponibles(proyecto_tmp) == []
    assert not (proyecto_tmp / "escenarios").exists() or not any((proyecto_tmp / "escenarios").iterdir())


@pytest.mark.parametrize("ext", [".exe", ".gif", ".txt", ""])
def test_solo_se_aceptan_imagenes_y_mp4(proyecto_tmp, ext):
    f = proyecto_tmp / "t" / "x.bin"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    with pytest.raises(ErrorAccionable) as exc:
        logica.agregar_escenario(proyecto_tmp, "x", ext, f)
    assert "png" in str(exc.value).lower() and "mp4" in str(exc.value).lower()


def test_un_webp_se_convierte_a_png(proyecto_tmp):
    ruta = proyecto_tmp / "t" / "w.webp"
    ruta.parent.mkdir(parents=True)
    Image.new("RGB", (1280, 720), (1, 2, 3)).save(ruta)
    e = logica.agregar_escenario(proyecto_tmp, "web", ".webp", ruta)
    assert (proyecto_tmp / "escenarios" / e["carpeta"] / "fondo.png").is_file()


def test_un_archivo_corrupto_se_rechaza_con_una_accion(proyecto_tmp):
    f = proyecto_tmp / "t" / "roto.png"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"no soy una imagen")
    with pytest.raises(ErrorAccionable):
        logica.agregar_escenario(proyecto_tmp, "roto", ".png", f)
    assert logica.escenarios_disponibles(proyecto_tmp) == []


def test_reemplazar_un_fondo_conserva_su_numero_y_guarda_el_anterior(proyecto_tmp):
    e = logica.agregar_escenario(proyecto_tmp, "calle", ".png", _png(proyecto_tmp / "t" / "a.png", color=(1, 1, 1)))
    r = logica.agregar_escenario(proyecto_tmp, "calle", ".jpg", _png(proyecto_tmp / "t" / "b.jpg", color=(200, 200, 200)), reemplazar="E1")
    assert r["id"] == "E1" and r["carpeta"] == e["carpeta"]
    carpeta = proyecto_tmp / "escenarios" / e["carpeta"]
    assert (carpeta / "fondo.jpg").is_file() and not (carpeta / "fondo.png").exists()
    assert list((proyecto_tmp / "escenarios" / "_papelera").glob("E1_*"))               # el fondo anterior no se pierde
    with pytest.raises(ErrorAccionable):
        logica.agregar_escenario(proyecto_tmp, "x", ".png", _png(proyecto_tmp / "t" / "c.png"), reemplazar="E99")


def test_un_reemplazo_malo_no_destruye_el_fondo_que_habia(proyecto_tmp):
    e = logica.agregar_escenario(proyecto_tmp, "calle", ".png", _png(proyecto_tmp / "t" / "a.png"))
    with pytest.raises(ErrorAccionable):
        logica.agregar_escenario(proyecto_tmp, "calle", ".png", _png(proyecto_tmp / "t" / "mal.png", (1000, 1000)), reemplazar="E1")
    assert (proyecto_tmp / "escenarios" / e["carpeta"] / "fondo.png").is_file()


def test_quitar_un_escenario_lo_mueve_a_la_papelera(proyecto_tmp):
    e = logica.agregar_escenario(proyecto_tmp, "calle", ".png", _png(proyecto_tmp / "t" / "a.png"))
    logica.quitar_escenario(proyecto_tmp, e["carpeta"])
    assert logica.escenarios_disponibles(proyecto_tmp) == []
    assert (proyecto_tmp / "escenarios" / "_papelera").is_dir()
    with pytest.raises(ErrorAccionable):
        logica.quitar_escenario(proyecto_tmp, "../personajes")


def test_la_miniatura_de_una_imagen_es_pequena_y_se_reutiliza(proyecto_tmp):
    e = logica.agregar_escenario(proyecto_tmp, "calle", ".png", _png(proyecto_tmp / "t" / "a.png", (3840, 2160)))
    m = logica.miniatura_escenario(proyecto_tmp, e["carpeta"])
    with Image.open(m) as im:
        assert im.width <= 480 and abs(im.width / im.height - 16 / 9) < 0.02
    assert logica.miniatura_escenario(proyecto_tmp, e["carpeta"]) == m


@pytest.mark.skipif(not rutas.FFMPEG.exists(), reason="falta ffmpeg")
def test_agregar_un_video_valida_duracion_y_saca_miniatura(proyecto_tmp):
    video = proyecto_tmp / "t" / "v.mp4"
    video.parent.mkdir(parents=True)
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=3",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    e = logica.agregar_escenario(proyecto_tmp, "video", ".mp4", video)
    assert e["tipo"] == "video" and (e["ancho"], e["alto"]) == (640, 360) and e["aviso"]          # menor que 1280x720: avisa
    assert logica.miniatura_escenario(proyecto_tmp, e["carpeta"]).is_file()
    corto = proyecto_tmp / "t" / "corto.mp4"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=0.5",
                    "-pix_fmt", "yuv420p", str(corto)], check=True)
    with pytest.raises(ErrorAccionable) as exc:
        logica.agregar_escenario(proyecto_tmp, "corto", ".mp4", corto)
    assert "segundo" in str(exc.value)


# ---------------- HTTP ----------------
@pytest.fixture
def srv(proyecto_tmp):
    servidor = crear_servidor(proyecto_tmp, 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield proyecto_tmp, f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def _png_bytes(tam=(1920, 1080)):
    b = io.BytesIO()
    Image.new("RGB", tam, (10, 120, 200)).save(b, "PNG")
    return b.getvalue()


def _subir(url, nombre, contenido, archivo="fondo.png", cabeceras=None, extra=""):
    h = {"Content-Type": "application/octet-stream", "X-Lipsync": "1", **(cabeceras or {})}
    req = urllib.request.Request(f"{url}/api/escenarios?nombre={quote(nombre)}&archivo={quote(archivo)}{extra}", data=contenido, headers=h,
                                 method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(url, ruta):
    try:
        with urllib.request.urlopen(url + ruta) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _post_json(url, ruta, cuerpo):
    req = urllib.request.Request(url + ruta, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", "X-Lipsync": "1"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_subir_listar_ver_y_quitar_un_escenario_por_http(srv):
    raiz, url = srv
    codigo, e = _subir(url, "Salón", _png_bytes())
    assert codigo == 200 and e["id"] == "E1" and e["tipo"] == "imagen"
    estado = json.loads(_get(url, "/api/estado")[1])
    assert [x["id"] for x in estado["escenarios"]] == ["E1"] and estado["escenarios"][0]["carpeta"] == e["carpeta"]
    codigo, cuerpo, cab = _get(url, f"/miniaturas/{e['carpeta']}.jpg")
    assert codigo == 200 and cab["Content-Type"] == "image/jpeg" and cuerpo[:2] == b"\xff\xd8"
    assert _post_json(url, f"/api/escenarios/{e['carpeta']}/eliminar", {}) == {"ok": True}
    assert json.loads(_get(url, "/api/estado")[1])["escenarios"] == []


def test_subir_un_escenario_sin_la_cabecera_de_seguridad_se_rechaza(srv):
    _, url = srv
    req = urllib.request.Request(f"{url}/api/escenarios?nombre=x&archivo=a.png", data=_png_bytes(),
                                 headers={"Content-Type": "application/octet-stream"}, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 403


def test_un_fondo_malo_da_error_en_espanol_y_no_deja_restos(srv):
    raiz, url = srv
    codigo, d = _subir(url, "cuadrado", _png_bytes((900, 900)))
    assert codigo == 400 and "16:9" in d["error"]
    codigo, d = _subir(url, "virus", b"MZ", archivo="virus.exe")
    assert codigo == 400 and "mp4" in d["error"].lower()
    assert json.loads(_get(url, "/api/estado")[1])["escenarios"] == []
    assert not (raiz / "cache" / "subidas").exists() or not any((raiz / "cache" / "subidas").iterdir())


def test_el_nombre_subido_no_puede_escapar_de_la_carpeta_de_escenarios(srv):
    raiz, url = srv
    codigo, e = _subir(url, "../../../../evil", _png_bytes(), archivo="../../x.png")
    assert codigo == 200 and ".." not in e["carpeta"] and "/" not in e["carpeta"] and "\\" not in e["carpeta"]
    assert (raiz / "escenarios" / e["carpeta"] / "fondo.png").is_file()
    assert not (raiz.parent / "evil").exists()


def test_una_miniatura_con_nombre_peligroso_o_inexistente_no_se_entrega(srv):
    _, url = srv
    for ruta in ("/miniaturas/..%2Ftts.jpg", "/miniaturas/E9_no.jpg", "/miniaturas/..%5C..%5Cx.jpg"):
        assert _get(url, ruta)[0] in (400, 404)
