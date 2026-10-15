"""T097 (FR-059): alineación de cabezas en el cambio de pose. La cabeza de cada pose se lleva al
mismo sitio que la de la pose de referencia (por el centro de la silueta de la cabeza), y las bocas
se desplazan igual; con la alineación apagada las poses quedan donde las dibujó la IA."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.alineacion import centro_cabeza, desplazamiento_alineacion
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import cargar_pose
from src.biblioteca.validacion import VISEMAS
from src.compositor import Compositor
from src.errores import AssetInvalido
from src.layers.base import CapaRGBA, ContextoFrame
from src.layers.camara import Ventana, ventana_plano
from src.timeline import Toma

LIENZO = (320, 180)
PIEL = (230, 180, 150, 255)
CUERPO = (245, 245, 245, 255)


def _pose(raiz, nombre, cabeza, con_brazo=False, lienzo=LIENZO, gesto_n=None):
    """Pose sintética: cabeza (disco de piel) en `cabeza`, tronco que llega al borde inferior y,
    opcionalmente, un brazo levantado lejos de la cabeza."""
    carpeta = raiz / "personajes" / "p" / "poses" / nombre
    (carpeta / "bocas").mkdir(parents=True, exist_ok=True)
    w, h = lienzo
    im = Image.new("RGBA", lienzo, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = cabeza
    d.rectangle((cx - 40, cy + 25, cx + 40, h), fill=CUERPO)                       # tronco hasta el borde inferior
    d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=PIEL)                      # cabeza
    if con_brazo:
        d.rectangle((cx - 90, cy + 50, cx - 70, cy + 80), fill=CUERPO)              # brazo bajo el nivel de la cabeza
    im.save(carpeta / "cuerpo.png")
    for v in VISEMAS:
        spr = Image.new("RGBA", (24, 12), (255, 0, 0, 255))
        spr.save(carpeta / "bocas" / f"{v}.png")
    formas = {v: {"x": cx, "y": cy + 15, "s": 1.0, "r": 0.0, "m": False} for v in VISEMAS}
    partes = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, partes[0], partes[1], int(partes[2]), lienzo, formas)
    return cargar_pose(carpeta)


def _ctx(pose_id, visema="D"):
    return ContextoFrame(n_frame=0, t=0.0, salida=LIENZO, toma=Toma(0, "E1", pose_id, "PL1"), visema=visema,
                         parpadeando=False, escala=1.0, dx=0.0, dy=0.0)


def _centro_de_color(img, color, tol=6):
    a = np.asarray(img.convert("RGB")).astype(int)
    m = (np.abs(a - np.array(color[:3])).max(2) <= tol)
    ys, xs = np.where(m)
    assert len(xs) > 50, "no se encontró el color buscado"
    return xs.mean(), ys.mean()


def _personaje(poses, alinear=True, referencia=None):
    from src.layers.personaje import PersonajeLayer
    ref = next(iter(poses.values()))
    return PersonajeLayer(poses, ventana_plano(ref, "PL1"), LIENZO, alinear=alinear, referencia=referencia)


# ---------------- centro de la cabeza ----------------
def test_el_centro_de_la_cabeza_sigue_a_la_cabeza(proyecto_tmp):
    a = _pose(proyecto_tmp, "frontal_neutro_01", (160, 60))
    b = _pose(proyecto_tmp, "frontal_explicar_01", (190, 80))
    ca = centro_cabeza(Image.open(a.ruta / "cuerpo.png"))
    cb = centro_cabeza(Image.open(b.ruta / "cuerpo.png"))
    assert (cb[0] - ca[0], cb[1] - ca[1]) == pytest.approx((30, 20), abs=1.0)


def test_un_brazo_levantado_no_mueve_el_centro_de_la_cabeza(proyecto_tmp):
    sin = _pose(proyecto_tmp, "frontal_neutro_01", (160, 60))
    con = _pose(proyecto_tmp, "frontal_pulgar_01", (160, 60), con_brazo=True)
    assert centro_cabeza(Image.open(sin.ruta / "cuerpo.png")) == pytest.approx(
        centro_cabeza(Image.open(con.ruta / "cuerpo.png")), abs=0.5)


def test_el_desplazamiento_lleva_la_cabeza_a_la_referencia():
    assert desplazamiento_alineacion((190.0, 80.0), (160.0, 60.0)) == (-30.0, -20.0)


def test_una_imagen_sin_silueta_da_un_error_claro():
    with pytest.raises(AssetInvalido) as exc:
        centro_cabeza(Image.new("RGBA", (64, 64), (0, 0, 0, 0)))
    assert "cabeza" in str(exc.value).lower()


# ---------------- el personaje con varias poses ----------------
@pytest.fixture
def dos_poses(proyecto_tmp):
    a = _pose(proyecto_tmp, "frontal_neutro_01", (160, 60))
    b = _pose(proyecto_tmp, "frontal_explicar_01", (190, 80))
    return {a.id: a, b.id: b}


def test_con_alineacion_la_cabeza_queda_en_el_mismo_sitio_en_las_dos_poses(dos_poses):
    comp = Compositor([_personaje(dos_poses)], LIENZO)
    ca = _centro_de_color(comp.componer(_ctx("frontal_neutro_01")), PIEL)
    cb = _centro_de_color(comp.componer(_ctx("frontal_explicar_01")), PIEL)
    assert cb == pytest.approx(ca, abs=1.5)


def test_sin_alineacion_las_cabezas_quedan_donde_se_dibujaron(dos_poses):
    comp = Compositor([_personaje(dos_poses, alinear=False)], LIENZO)
    ca = _centro_de_color(comp.componer(_ctx("frontal_neutro_01")), PIEL)
    cb = _centro_de_color(comp.componer(_ctx("frontal_explicar_01")), PIEL)
    assert (cb[0] - ca[0], cb[1] - ca[1]) == pytest.approx((30, 20), abs=1.5)


def test_se_puede_elegir_la_pose_de_referencia(dos_poses):
    comp = Compositor([_personaje(dos_poses, referencia="frontal_explicar_01")], LIENZO)
    cb = _centro_de_color(comp.componer(_ctx("frontal_explicar_01")), PIEL)
    ca = _centro_de_color(comp.componer(_ctx("frontal_neutro_01")), PIEL)
    assert cb == pytest.approx((190, 80), abs=2.0) and ca == pytest.approx(cb, abs=1.5)


def test_la_boca_se_mueve_junto_con_el_cuerpo(dos_poses):
    comp = Compositor([_personaje(dos_poses)], LIENZO)
    base = comp.componer(_ctx("frontal_neutro_01"))
    otra = comp.componer(_ctx("frontal_explicar_01"))
    b0, b1 = _centro_de_color(base, (255, 0, 0)), _centro_de_color(otra, (255, 0, 0))
    assert b1 == pytest.approx(b0, abs=1.5)               # cabezas alineadas -> bocas en el mismo sitio
    # y la boca sigue donde la calibraron respecto de la cabeza (15 px más abajo que su centro)
    cabeza = _centro_de_color(otra, PIEL)
    assert b1[1] - cabeza[1] == pytest.approx(15, abs=6)
    sin_alinear = Compositor([_personaje(dos_poses, alinear=False)], LIENZO).componer(_ctx("frontal_explicar_01"))
    assert _centro_de_color(sin_alinear, (255, 0, 0))[0] == pytest.approx(190, abs=1.5)


def test_el_cuerpo_desplazado_no_deja_huecos_en_el_borde_inferior(dos_poses):
    frame = Compositor([_personaje(dos_poses)], LIENZO).componer(_ctx("frontal_explicar_01"))
    px = frame.getpixel((LIENZO[0] // 2, LIENZO[1] - 1))
    assert px[:3] == CUERPO[:3]                            # se replican los bordes: el tronco llega hasta abajo


def test_sin_toma_se_usa_la_primera_pose(dos_poses):
    ctx = ContextoFrame(0, 0.0, LIENZO, None, "D", False, 1.0, 0.0, 0.0)
    assert Compositor([_personaje(dos_poses)], LIENZO).componer(ctx).size == LIENZO


def test_pedir_una_pose_que_no_existe_da_un_error_claro(dos_poses):
    with pytest.raises(AssetInvalido) as exc:
        Compositor([_personaje(dos_poses)], LIENZO).componer(_ctx("frontal_inexistente_09"))
    assert "frontal_inexistente_09" in str(exc.value)


def test_poses_con_lienzos_distintos_se_rechazan(proyecto_tmp):
    a = _pose(proyecto_tmp, "frontal_neutro_01", (160, 60))
    b = _pose(proyecto_tmp, "frontal_explicar_01", (190, 80), lienzo=(640, 360))
    with pytest.raises(AssetInvalido) as exc:
        _personaje({a.id: a, b.id: b})
    assert "lienzo" in str(exc.value).lower()


def test_el_centro_de_la_cabeza_se_lee_de_config_si_esta_calculado(proyecto_tmp):
    a = _pose(proyecto_tmp, "frontal_neutro_01", (160, 60))
    b = _pose(proyecto_tmp, "frontal_explicar_01", (190, 80))
    import yaml
    for p, pelo in ((a, (160.0, 50.0)), (b, (170.0, 60.0))):                # valores inventados: deben mandar
        cfg = yaml.safe_load((p.ruta / "config.yaml").read_text(encoding="utf-8"))
        cfg["pelo"] = list(pelo)
        (p.ruta / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    a, b = cargar_pose(a.ruta), cargar_pose(b.ruta)
    comp = Compositor([_personaje({a.id: a, b.id: b})], LIENZO)
    ca = _centro_de_color(comp.componer(_ctx(a.id)), PIEL)
    cb = _centro_de_color(comp.componer(_ctx(b.id)), PIEL)
    assert (cb[0] - ca[0], cb[1] - ca[1]) == pytest.approx((30 - (170 - 160), 20 - (60 - 50)), abs=1.5)


def test_solo_se_guardan_las_poses_usadas_recientemente(proyecto_tmp):
    from src.layers.personaje import PersonajeLayer
    poses = {}
    for i in range(1, 8):
        p = _pose(proyecto_tmp, f"frontal_neutro_{i:02d}", (160 + i, 60))
        poses[p.id] = p
    capa = PersonajeLayer(poses, ventana_plano(next(iter(poses.values())), "PL1"), LIENZO, max_poses_en_memoria=3)
    for pid in poses:
        capa.renderizar(_ctx(pid))
    assert capa.poses_en_memoria <= 3


# ---------------- el compositor con capas de varias imágenes ----------------
def test_el_compositor_apila_las_imagenes_que_devuelve_una_capa():
    class Doble:
        def renderizar(self, ctx):
            return [CapaRGBA(Image.new("RGBA", (10, 10), (255, 0, 0, 255)), 0, 0),
                    CapaRGBA(Image.new("RGBA", (4, 4), (0, 255, 0, 255)), 2, 2)]
    frame = Compositor([Doble()], (16, 16)).componer(_ctx("x"))
    assert frame.getpixel((0, 0)) == (255, 0, 0) and frame.getpixel((3, 3)) == (0, 255, 0)


# ---------------- tomas provisionales (hasta el director, T070) ----------------
def test_tomas_ciclicas_cortan_en_pausas_y_alternan_poses():
    from src.timeline import Visema, tomas_ciclicas
    fps, n = 25, 25 * 120
    visemas, f = [], 0
    while f < n:                                        # habla 4 s, pausa 1 s, y así hasta el final
        visemas.append(Visema(f, min(f + 100, n), "D")); f += 100
        if f < n:
            visemas.append(Visema(f, min(f + 25, n), "X")); f += 25
    tomas = tomas_ciclicas(["a", "b", "c"], visemas, n, fps, "E1", "PL1", duracion_toma_s=20.0)
    assert tomas[0].f0 == 0 and [t.f0 for t in tomas] == sorted({t.f0 for t in tomas})
    assert len(tomas) == 6                              # 120 s / 20 s
    assert all(x.pose != y.pose for x, y in zip(tomas, tomas[1:]))
    pausas = {v.f0 for v in visemas if v.v == "X"}
    assert all(t.f0 in pausas for t in tomas[1:])       # cada corte cae al inicio de una pausa
    assert tomas == tomas_ciclicas(["a", "b", "c"], visemas, n, fps, "E1", "PL1", duracion_toma_s=20.0)


def test_una_sola_pose_da_una_sola_toma():
    from src.timeline import Visema, tomas_ciclicas
    assert len(tomas_ciclicas(["a"], [Visema(0, 500, "D")], 500, 25, "E1", "PL1")) == 1
