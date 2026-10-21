"""El editor de escenas en la interfaz: subir la capa delantera, leer y guardar la configuración y pedir la vista previa por HTTP."""
import io
import json
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.validacion import VISEMAS
from src.errores import ErrorAccionable
from src.ui import logica
from src.ui.servidor import crear_servidor

POSE = (640, 360)
ESCENA = (1280, 720)


def _pose(raiz, nombre):
    carpeta = raiz / "personajes" / "profesor" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", POSE, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((230, 175, 410, 360), fill=(245, 245, 245, 255))
    d.ellipse((260, 60, 380, 180), fill=(230, 180, 150, 255))
    im.save(carpeta / "cuerpo.png")
    for v in VISEMAS:
        Image.new("RGBA", (50, 20), (200, 20, 20, 255)).save(carpeta / "bocas" / f"{v}.png")
    Image.new("RGBA", (60, 14), (20, 20, 20, 255)).save(carpeta / "parpadeo_cerrado.png")
    formas = {v: {"x": 320, "y": 160, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), POSE, formas,
                            parpadeo={"parche": {"x": 290, "y": 93}, "cerrado": "parpadeo_cerrado.png", "medio": None})


def _escenario(raiz, con_frente=False):
    carpeta = raiz / "escenarios" / "E1_oficina"
    carpeta.mkdir(parents=True)
    fondo = Image.new("RGBA", ESCENA, (30, 40, 40, 255))
    ImageDraw.Draw(fondo).ellipse((900, 100, 960, 160), fill=(255, 230, 170, 255))              # una lámpara
    fondo.save(carpeta / "fondo.png")
    if con_frente:
        frente = Image.new("RGBA", ESCENA, (0, 0, 0, 0))
        ImageDraw.Draw(frente).rectangle((0, 560, 1279, 719), fill=(255, 0, 255, 255))
        frente.save(carpeta / "frente.png")
    return carpeta


def _png(tam=ESCENA, transparente=True):
    im = Image.new("RGBA", tam, (0, 0, 0, 0) if transparente else (255, 0, 255, 255))
    if transparente:
        ImageDraw.Draw(im).rectangle((0, tam[1] * 3 // 4, tam[0], tam[1]), fill=(255, 0, 255, 255))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


@pytest.fixture
def mundo(proyecto_tmp):
    _pose(proyecto_tmp, "frontal_neutro_01")
    _pose(proyecto_tmp, "frontal_explicar_01")
    _escenario(proyecto_tmp, con_frente=True)
    return proyecto_tmp


@pytest.fixture
def srv(mundo):
    servidor = crear_servidor(mundo, 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield mundo, f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def _pedir(url, ruta, cuerpo=None, cabeceras=None, crudo=None):
    h = {"X-Lipsync": "1", **(cabeceras or {})}
    datos = crudo
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url + ruta, data=datos, headers=h, method="POST" if datos is not None else "GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


# ---------------- la capa delantera ----------------
def test_subir_el_frente_crea_la_configuracion_con_luces_detectadas(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    origen = proyecto_tmp / "f.png"
    origen.write_bytes(_png())
    r = logica.subir_frente(proyecto_tmp, carpeta.name, origen)
    assert r["capas"] is True and r["luces_detectadas"] >= 1
    assert (carpeta / "frente.png").is_file() and (carpeta / "escena.yaml").is_file()
    assert [e["capas"] for e in logica.escenarios_disponibles(proyecto_tmp)] == [True]


def test_un_frente_sin_transparencia_o_de_otro_tamano_se_rechaza_sin_tocar_nada(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    for contenido, texto in ((_png(transparente=False), "transparencia"), (_png((640, 360)), "mismo tamaño"), (b"no soy una imagen", "imagen")):
        origen = proyecto_tmp / "f.png"
        origen.write_bytes(contenido)
        with pytest.raises(ErrorAccionable) as exc:
            logica.subir_frente(proyecto_tmp, carpeta.name, origen)
        assert texto in str(exc.value)
    assert not (carpeta / "frente.png").exists() and not (carpeta / "escena.yaml").exists()


def test_subir_el_frente_a_un_escenario_inexistente_o_peligroso_falla(proyecto_tmp):
    origen = proyecto_tmp / "f.png"
    origen.write_bytes(_png())
    for malo in ("E9_no", "../personajes", "x"):
        with pytest.raises(ErrorAccionable):
            logica.subir_frente(proyecto_tmp, malo, origen)


# ---------------- configuración por HTTP ----------------
def test_leer_modificar_y_guardar_la_configuracion_por_http(srv):
    raiz, url = srv
    codigo, cuerpo, _ = _pedir(url, "/api/escenas/E1_oficina/config")
    d = json.loads(cuerpo)
    assert codigo == 200 and d["config"]["lienzo"] == [1280, 720] and d["planos"][0] == "PL1"
    assert {p["id"] for p in d["poses"]} == {"frontal_neutro_01", "frontal_explicar_01"}
    d["config"]["personaje"]["escala"] = 0.9
    d["config"]["poses_permitidas"] = ["frontal_neutro_01"]
    codigo, cuerpo, _ = _pedir(url, "/api/escenas/E1_oficina/config", {"config": d["config"]})
    assert codigo == 200 and json.loads(cuerpo)["config"]["personaje"]["escala"] == 0.9
    otra = json.loads(_pedir(url, "/api/escenas/E1_oficina/config")[1])["config"]
    assert otra["personaje"]["escala"] == 0.9 and otra["poses_permitidas"] == ["frontal_neutro_01"]


def test_una_configuracion_mala_da_error_en_espanol_y_no_se_guarda(srv):
    raiz, url = srv
    cfg = json.loads(_pedir(url, "/api/escenas/E1_oficina/config")[1])["config"]
    guardado_antes = (raiz / "escenarios" / "E1_oficina" / "escena.yaml").exists()
    cfg["personaje"]["escala"] = 50
    codigo, cuerpo, _ = _pedir(url, "/api/escenas/E1_oficina/config", {"config": cfg})
    assert codigo == 400 and "escala" in json.loads(cuerpo)["error"]
    assert (raiz / "escenarios" / "E1_oficina" / "escena.yaml").exists() == guardado_antes
    assert _pedir(url, "/api/escenas/E1_oficina/config", {"config": {"x": 1}})[0] == 400


def test_guardar_la_configuracion_sin_la_cabecera_de_seguridad_se_rechaza(srv):
    _, url = srv
    req = urllib.request.Request(url + "/api/escenas/E1_oficina/config", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 403


def test_subir_el_frente_por_http(srv):
    raiz, url = srv
    (raiz / "escenarios" / "E1_oficina" / "frente.png").unlink()
    codigo, cuerpo, _ = _pedir(url, "/api/escenas/E1_oficina/frente", crudo=_png(), cabeceras={"Content-Type": "application/octet-stream"})
    assert codigo == 200 and json.loads(cuerpo)["capas"] is True
    codigo, cuerpo, _ = _pedir(url, "/api/escenas/E1_oficina/frente", crudo=_png((100, 100)), cabeceras={"Content-Type": "application/octet-stream"})
    assert codigo == 400 and "mismo tamaño" in json.loads(cuerpo)["error"]


def test_una_escena_sin_capas_no_se_puede_editar(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    with pytest.raises(ErrorAccionable) as exc:
        logica.config_escena(proyecto_tmp, carpeta.name)
    assert "frente" in str(exc.value)


# ---------------- vista previa ----------------
def _vista(url, config, **kw):
    cuerpo = {"config": config, "pose": "frontal_neutro_01", "plano": "PL2", "visema": "D", "ojos": "abierto", "luz": False, "borrador": True, **kw}
    return _pedir(url, "/api/escenas/E1_oficina/vista", cuerpo)


def test_la_vista_previa_devuelve_un_jpeg_con_la_ventana_del_plano(srv):
    raiz, url = srv
    cfg = json.loads(_pedir(url, "/api/escenas/E1_oficina/config")[1])["config"]
    codigo, cuerpo, cab = _vista(url, cfg)
    assert codigo == 200 and cab["Content-Type"] == "image/jpeg" and cuerpo[:2] == b"\xff\xd8"
    x0, y0, w, h = (float(v) for v in cab["X-Ventana"].split(","))
    assert abs(w / h - 16 / 9) < 1e-3 and w <= 1280
    assert Image.open(io.BytesIO(cuerpo)).size == (640, 360)
    _, final, _ = _vista(url, cfg, borrador=False)
    assert Image.open(io.BytesIO(final)).size == (960, 540)


def test_mover_al_personaje_en_la_configuracion_mueve_la_boca_en_la_vista_previa(srv):
    raiz, url = srv
    cfg = json.loads(_pedir(url, "/api/escenas/E1_oficina/config")[1])["config"]
    cfg["personaje"].update({"cabeza": [700, 250], "escala": 1.0})

    def boca(config):
        a = np.asarray(Image.open(io.BytesIO(_vista(url, config, plano="PL1")[1])).convert("RGB")).astype(int)   # PL1: toda la escena, la cámara no se mueve
        m = (a[..., 0] > 2 * a[..., 1]) & (a[..., 0] > 2 * a[..., 2]) & (a[..., 0] > 150) & (a[..., 1] < 80)
        ys, xs = np.where(m)
        return xs.mean(), ys.mean()
    x1, y1 = boca(cfg)
    cfg["personaje"]["cabeza"] = [760, 280]
    x2, y2 = boca(cfg)
    assert x2 > x1 + 10 and y2 > y1 + 10                                                        # se movió hacia la derecha y abajo
    guardado = (raiz / "escenarios" / "E1_oficina" / "escena.yaml")
    assert not guardado.exists() or "760" not in guardado.read_text(encoding="utf-8")          # la vista previa no guarda nada


@pytest.mark.parametrize("cambio, texto", [({"pose": "frontal_no_existe_09"}, "no existe"), ({"plano": "PL9"}, "PL9"),
                                          ({"visema": "Z"}, "Z"), ({"ojos": "dormido"}, "dormido")])
def test_pedir_una_vista_con_datos_malos_da_un_error_claro(srv, cambio, texto):
    raiz, url = srv
    cfg = json.loads(_pedir(url, "/api/escenas/E1_oficina/config")[1])["config"]
    codigo, cuerpo, _ = _vista(url, cfg, **cambio)
    assert codigo == 400 and texto in json.loads(cuerpo)["error"]


def test_los_parpadeos_y_la_luz_funcionan_en_la_vista_previa(srv):
    raiz, url = srv
    cfg = json.loads(_pedir(url, "/api/escenas/E1_oficina/config")[1])["config"]
    abiertos = np.asarray(Image.open(io.BytesIO(_vista(url, cfg, ojos="abierto")[1])).convert("RGB")).astype(int)
    cerrados = np.asarray(Image.open(io.BytesIO(_vista(url, cfg, ojos="cerrado")[1])).convert("RGB")).astype(int)
    assert (np.abs(abiertos - cerrados).max(2) > 40).sum() > 50
    con = np.asarray(Image.open(io.BytesIO(_vista(url, cfg, luz=True)[1])).convert("RGB")).astype(int)
    sin = np.asarray(Image.open(io.BytesIO(_vista(url, cfg, luz=False)[1])).convert("RGB")).astype(int)
    assert np.abs(con - sin).mean() > 0.5
