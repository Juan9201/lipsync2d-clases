"""Escenarios con capas: configuración, composición (fondo · personaje · frente) y, sobre todo, que la boca y los parpadeos
no se descoloquen al mover, escalar, hacer zoom o iluminar al personaje."""
import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import VISEMAS
from src.errores import AssetInvalido, ErrorAccionable
from src.escena import config as cfgmod
from src.escena.escena import EscenaLayer, activos_de, ventana_de_plano

ESCENA = (1280, 720)
POSE = (640, 360)
PIEL = (230, 180, 150)
BOCA = (200, 20, 20)
OJOS = (20, 20, 20)
PARED = (60, 70, 80)


def _pose(raiz, nombre, cabeza=(320, 120), boca=(320, 160), ojos=(320, 100)):
    carpeta = raiz / "personajes" / "p" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", POSE, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((cabeza[0] - 90, cabeza[1] + 55, cabeza[0] + 90, POSE[1]), fill=(245, 245, 245, 255))
    d.ellipse((cabeza[0] - 60, cabeza[1] - 60, cabeza[0] + 60, cabeza[1] + 60), fill=(*PIEL, 255))
    im.save(carpeta / "cuerpo.png")
    for i, v in enumerate(VISEMAS):
        Image.new("RGBA", (50, 20), (*BOCA, 255)).save(carpeta / "bocas" / f"{v}.png")
    Image.new("RGBA", (60, 14), (*OJOS, 255)).save(carpeta / "parpadeo_cerrado.png")
    formas = {v: {"x": boca[0], "y": boca[1], "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    p = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, p[0], p[1], int(p[2]), POSE, formas,
                            parpadeo={"parche": {"x": ojos[0] - 30, "y": ojos[1] - 7}, "cerrado": "parpadeo_cerrado.png", "medio": None})
    return cargar_pose(carpeta)


def _escenario(raiz, frente_bloque=None, tam=ESCENA):
    carpeta = raiz / "escenarios" / "E1_prueba"
    carpeta.mkdir(parents=True)
    fondo = Image.new("RGBA", tam, (0, 0, 0, 0))
    ImageDraw.Draw(fondo).rectangle((0, 0, 100, 100), fill=(0, 255, 0, 255))              # un objeto detrás
    fondo.save(carpeta / "fondo.png")
    frente = Image.new("RGBA", tam, (0, 0, 0, 0))
    if frente_bloque:
        ImageDraw.Draw(frente).rectangle(frente_bloque, fill=(255, 0, 255, 255))           # un objeto delante
    frente.save(carpeta / "frente.png")
    return carpeta


def _config(carpeta, **cambios):
    cfg = cfgmod.cargar_config(carpeta)
    cfg["luz"]["luces"] = []
    cfg["pared"] = {"arriba": list(PARED), "abajo": list(PARED)}
    for k, v in cambios.items():
        if k in ("cabeza", "escala"):
            cfg["personaje"][k] = v
        else:
            cfg[k] = v
    return cfg


def _marca(img, que):
    """Centro y tamaño de lo rojizo (boca) u oscuro (parche de ojos) aunque la luz haya cambiado sus colores."""
    a = np.asarray(img.convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (r > 2 * g) & (r > 2 * b) & (r > 50) if que == "boca" else (np.maximum(np.maximum(r, g), b) < 55)
    ys, xs = np.where(m)
    return (xs.mean(), ys.mean(), len(xs)) if len(xs) else None


def _buscar(img, color, tol=12):
    a = np.asarray(img.convert("RGB")).astype(int)
    m = np.abs(a - np.array(color)).max(2) <= tol
    ys, xs = np.where(m)
    return (xs.mean(), ys.mean(), len(xs)) if len(xs) else None


def _esperado(capa, pose, plano, x, y):
    """Dónde debe caer, en el cuadro, un punto (x, y) del lienzo de la pose."""
    qx = capa._esc * x + capa._t[0]
    qy = capa._esc * y + capa._t[1]
    return capa.a_pantalla(qx, qy, plano)


# ---------------- la boca y los parpadeos no se descolocan ----------------
@pytest.mark.parametrize("escala, cabeza, plano", [(0.8, (900, 300), "PL3"), (1.2, (700, 250), "PL4"), (0.5, (500, 350), "PL2"),
                                                    (1.0, (640, 360), "PL5"), (0.65, (1000, 200), "PL1")])
@pytest.mark.parametrize("con_luz", [False, True])
def test_la_boca_y_los_ojos_caen_donde_deben_con_cualquier_escala_posicion_plano_y_luz(proyecto_tmp, escala, cabeza, plano, con_luz):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    carpeta = _escenario(proyecto_tmp)
    cfg = _config(carpeta, cabeza=list(cabeza), escala=escala)
    cfg["luz"]["luces"] = [{"nombre": "l", "pos": [300, 200], "color": [1, 0.8, 0.5], "fuerza": 1.0, "alcance": 800, "altura": 300}]
    capa = EscenaLayer(carpeta, cfg, {pose.id: pose}, ESCENA)
    boca = _marca(capa.vista(pose.id, plano, "D", "abierto", con_luz), "boca")
    ojos = _marca(capa.vista(pose.id, plano, "X", "cerrado", con_luz), "ojos")
    ex_b, ey_b = _esperado(capa, pose, plano, 320, 160)
    ex_o, ey_o = _esperado(capa, pose, plano, 320, 100)
    assert boca and ojos
    assert abs(boca[0] - ex_b) < 3 and abs(boca[1] - ey_b) < 3, (boca, (ex_b, ey_b))
    assert abs(ojos[0] - ex_o) < 3 and abs(ojos[1] - ey_o) < 3, (ojos, (ex_o, ey_o))


def test_la_luz_no_mueve_la_silueta_del_personaje(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    carpeta = _escenario(proyecto_tmp)
    cfg = _config(carpeta, cabeza=[800, 250], escala=0.8)
    cfg["luz"]["luces"] = [{"nombre": "l", "pos": [200, 200], "color": [1, 0.8, 0.5], "fuerza": 1.2, "alcance": 700, "altura": 300}]
    capa = EscenaLayer(carpeta, cfg, {pose.id: pose}, ESCENA)
    sin, con = capa.vista(pose.id, "PL3", con_luz=False), capa.vista(pose.id, "PL3", con_luz=True)
    quiere = lambda im: (np.abs(np.asarray(im).astype(int) - np.array(PARED)).max(2) > 10)
    assert (quiere(sin) == quiere(con)).mean() > 0.995                       # mismos píxeles ocupados; solo cambia el color
    assert np.abs(np.asarray(sin).astype(int) - np.asarray(con).astype(int)).mean() > 1      # y la luz sí cambia algo


def test_el_ajuste_fino_de_una_pose_la_mueve_en_la_escena_y_no_a_las_demas(proyecto_tmp):
    a, b = _pose(proyecto_tmp, "frontal_neutro_01"), _pose(proyecto_tmp, "frontal_explicar_01")
    carpeta = _escenario(proyecto_tmp)
    cfg = _config(carpeta, cabeza=[800, 250], escala=0.8)
    cfg["personaje"]["ajustes"] = {b.id: {"dx": 60, "dy": -20}}
    capa = EscenaLayer(carpeta, cfg, {a.id: a, b.id: b}, ESCENA)
    antes_a = _buscar(capa.vista(a.id, "PL1", "D"), BOCA)
    antes_b = _buscar(capa.vista(b.id, "PL1", "D"), BOCA)
    assert abs((antes_b[0] - antes_a[0]) - 60 * ESCENA[0] / capa.ventana_escena("PL1").w) < 3
    assert abs((antes_b[1] - antes_a[1]) - (-20) * ESCENA[0] / capa.ventana_escena("PL1").w) < 3
    cfg2 = _config(carpeta, cabeza=[800, 250], escala=0.8)
    sin = EscenaLayer(carpeta, cfg2, {a.id: a, b.id: b}, ESCENA)
    assert abs(_buscar(sin.vista(a.id, "PL1", "D"), BOCA)[0] - antes_a[0]) < 1       # la otra pose no se movió


# ---------------- orden de las capas ----------------
def test_el_frente_tapa_al_personaje_y_el_fondo_queda_detras(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    carpeta = _escenario(proyecto_tmp, frente_bloque=(0, 560, 1279, 719))                   # una «mesa» que cubre la parte baja
    cfg = _config(carpeta, cabeza=[640, 200], escala=1.0)
    im = EscenaLayer(carpeta, cfg, {pose.id: pose}, ESCENA).vista(pose.id, "PL1", con_luz=False)
    px = lambda x, y: tuple(im.getpixel((x, y)))
    assert px(640, 650)[:2] == (255, 0) and px(640, 650)[2] > 240          # abajo manda el frente
    assert px(30, 30) == (0, 255, 0)                                       # el objeto del fondo se ve donde no hay nada delante
    assert all(0.7 * e <= c <= e + 2 for c, e in zip(px(1200, 30), PARED))    # y la pared (con su viñeta suave) donde no hay nada
    assert _buscar(im, PIEL, 12) is not None                               # el personaje se ve por encima del fondo


def test_la_pared_solo_se_ve_si_el_fondo_tiene_transparencia(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    carpeta = _escenario(proyecto_tmp)
    Image.new("RGBA", ESCENA, (10, 200, 30, 255)).save(carpeta / "fondo.png")              # ahora el fondo es opaco
    im = EscenaLayer(carpeta, _config(carpeta), {pose.id: pose}, ESCENA).vista(pose.id, "PL1", con_luz=False)
    assert im.getpixel((1200, 30)) == (10, 200, 30)


# ---------------- cámara ----------------
def test_el_plano_pl1_es_toda_la_escena_y_los_cerrados_se_quedan_dentro_de_ella(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    v1 = ventana_de_plano("PL1", (900, 300), ESCENA, pose)
    assert (v1.x0, v1.y0, round(v1.w), round(v1.h)) == (0, 0, 1280, 720)
    for pl in ("PL2", "PL3", "PL4", "PL5", "PL6"):
        v = ventana_de_plano(pl, (1250, 700), ESCENA, pose)                                  # cabeza en una esquina
        assert v.x0 >= 0 and v.y0 >= 0 and v.x0 + v.w <= 1280 + 1e-6 and v.y0 + v.h <= 720 + 1e-6
        assert abs(v.w / v.h - 16 / 9) < 1e-6


def test_un_plano_inexistente_da_un_error_claro(proyecto_tmp):
    pose = _pose(proyecto_tmp, "frontal_neutro_01")
    carpeta = _escenario(proyecto_tmp)
    capa = EscenaLayer(carpeta, _config(carpeta), {pose.id: pose}, ESCENA, planos=["PL1", "PL3"])
    with pytest.raises(AssetInvalido) as exc:
        capa.vista(pose.id, "PL5")
    assert "PL5" in str(exc.value) and "PL3" in str(exc.value)


# ---------------- capas mal hechas ----------------
def test_capas_de_distinto_tamano_se_rechazan_diciendo_cual_y_por_que(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    Image.new("RGBA", (1000, 500), (0, 0, 0, 0)).save(carpeta / "frente.png")
    with pytest.raises(AssetInvalido) as exc:
        activos_de(carpeta)
    assert "1000x500" in str(exc.value) and "mismo tamaño" in str(exc.value)


def test_una_escena_sin_frente_no_se_puede_usar_y_dice_que_hacer(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    (carpeta / "frente.png").unlink()
    with pytest.raises(AssetInvalido) as exc:
        activos_de(carpeta)
    assert "frente" in str(exc.value)


# ---------------- configuración ----------------
def test_la_configuracion_inicial_trae_valores_razonables_y_luces_detectadas(proyecto_tmp):
    carpeta = proyecto_tmp / "escenarios" / "E1_x"
    carpeta.mkdir(parents=True)
    fondo = Image.new("RGBA", (1920, 1080), (20, 30, 30, 255))
    ImageDraw.Draw(fondo).ellipse((1400, 200, 1480, 280), fill=(255, 230, 180, 255))        # una lámpara brillante
    fondo.save(carpeta / "fondo.png")
    Image.new("RGBA", (1920, 1080), (0, 0, 0, 0)).save(carpeta / "frente.png")
    cfg = cfgmod.cargar_config(carpeta)
    assert cfg["lienzo"] == [1920, 1080] and cfg["personaje"]["escala"] == 0.6 and cfg["personaje"]["cabeza"] == [1382, 302]
    assert len(cfg["luz"]["luces"]) == 1
    x, y = cfg["luz"]["luces"][0]["pos"]
    assert abs(x - 1440) < 60 and abs(y - 240) < 60


def test_guardar_y_volver_a_leer_la_configuracion_conserva_todo(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    cfg = cfgmod.cargar_config(carpeta)
    cfg["personaje"].update({"cabeza": [700, 300], "escala": 0.9, "ajustes": {"frontal_neutro_01": {"dx": 5, "dy": -3}}})
    cfg["luz"]["luces"] = [{"nombre": "lámpara", "pos": [100, 120], "color": [1, 0.8, 0.5], "fuerza": 1.5, "alcance": 600, "altura": 200}]
    cfg["poses_permitidas"] = ["frontal_neutro_01"]
    cfgmod.guardar_config(carpeta, cfg)
    otra = cfgmod.cargar_config(carpeta)
    assert otra["personaje"]["cabeza"] == [700.0, 300.0] and otra["personaje"]["escala"] == 0.9
    assert otra["personaje"]["ajustes"] == {"frontal_neutro_01": {"dx": 5.0, "dy": -3.0}}
    assert otra["luz"]["luces"][0]["nombre"] == "lámpara" and otra["poses_permitidas"] == ["frontal_neutro_01"]
    assert yaml.safe_load((carpeta / "escena.yaml").read_text(encoding="utf-8"))["version"] == 1


@pytest.mark.parametrize("cambio, texto", [
    (lambda c: c["personaje"].update(escala=9), "escala"),
    (lambda c: c["personaje"].update(cabeza=[1, 2, 3]), "cabeza"),
    (lambda c: c["personaje"].update(cabeza=[99999, 0]), "cabeza"),
    (lambda c: c["mesa"].update(y=-5), "mesa"),
    (lambda c: c["luz"].update(ambiente=[0, 0]), "ambiente"),
    (lambda c: c["luz"].update(luces=[{"pos": [0, 0], "fuerza": 99}]), "luz 1"),
    (lambda c: c["luz"].update(luces=[{"pos": [0, 0]}] * 9), "luces"),
    (lambda c: c.update(poses_permitidas="todas"), "poses_permitidas"),
])
def test_una_configuracion_invalida_se_rechaza_nombrando_el_valor(proyecto_tmp, cambio, texto):
    carpeta = _escenario(proyecto_tmp)
    cfg = cfgmod.cargar_config(carpeta)
    cambio(cfg)
    with pytest.raises(ErrorAccionable) as exc:
        cfgmod.guardar_config(carpeta, cfg)
    assert texto in str(exc.value)
    assert not (carpeta / "escena.yaml").exists()                                             # no se guardó nada


def test_un_yaml_roto_da_un_error_claro(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    (carpeta / "escena.yaml").write_text("personaje: [", encoding="utf-8")
    with pytest.raises(ErrorAccionable):
        cfgmod.cargar_config(carpeta)


def test_se_reconoce_un_escenario_con_capas(proyecto_tmp):
    carpeta = _escenario(proyecto_tmp)
    assert cfgmod.es_escena(carpeta)
    (carpeta / "frente.png").unlink()
    assert not cfgmod.es_escena(carpeta)
