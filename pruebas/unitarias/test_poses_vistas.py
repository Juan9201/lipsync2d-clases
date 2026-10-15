"""T093 (FR-050, FR-051, FR-062, FR-067): poses por vista y gesto (<vista>_<gesto>_<NN>), calibración
de boca por forma (x, y, escala, giro, reflejo), reflejo de la pose combinado con el de la forma y
juego de bocas por vista."""
import pytest
import yaml
from PIL import Image, ImageDraw

from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.modelos import cargar_pose, espejo_de_forma
from src.biblioteca.validacion import VISEMAS, validar_pose
from src.errores import AssetInvalido
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.concretas import AnclasEstaticas, BocaLayer

LIENZO = (320, 180)
SALIDA = (160, 90)


def _sprite(i: int) -> Image.Image:
    """Boca asimétrica de tamaño propio: mitad izquierda roja, mitad derecha azul."""
    w, h = 40 + 4 * i, 20 + 2 * i
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w // 2 - 1, h - 1), fill=(255, 0, 0, 255))
    d.rectangle((w // 2, 0, w - 1, h - 1), fill=(0, 0, 255, 255))
    return im


FORMAS = {v: {"x": 150 + 2 * i, "y": 100 + i, "s": 1.5, "r": 0.0, "m": False} for i, v in enumerate(VISEMAS)}


def crear_pose_v4(raiz, nombre="tres_cuartos_der_neutro_01", formas=None, con_bocas=True, **kw):
    carpeta = raiz / "personajes" / "p" / "poses" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", LIENZO, (0, 0, 0, 0)).save(carpeta / "cuerpo.png")
    if con_bocas:
        (carpeta / "bocas").mkdir(exist_ok=True)
        for i, v in enumerate(VISEMAS):
            _sprite(i).save(carpeta / "bocas" / f"{v}.png")
    partes = nombre.rsplit("_", 2)
    escribir_config_pose_v4(carpeta, vista=partes[0], gesto=partes[1], variante=int(partes[2]), lienzo=LIENZO,
                            formas=formas if formas is not None else FORMAS, **kw)
    return carpeta


def _ctx(visema):
    return ContextoFrame(n_frame=0, t=0.0, salida=SALIDA, toma=None, visema=visema, parpadeando=False,
                         escala=1.0, dx=0.0, dy=0.0)


# ---------------- nomenclatura y modelo ----------------
def test_la_pose_v4_expone_vista_gesto_tipo_y_variante(proyecto_tmp):
    pose = cargar_pose(crear_pose_v4(proyecto_tmp, "tres_cuartos_der_explicar_01"))
    assert pose.id == "tres_cuartos_der_explicar_01"
    assert (pose.vista, pose.gesto, pose.variante) == ("tres_cuartos_der", "explicar", 1)
    assert pose.tipo == "estado"
    assert pose.formas["D"].s == 1.5 and pose.formas["D"].m is False


def test_el_tipo_sale_del_gesto_si_no_se_indica(proyecto_tmp):
    assert cargar_pose(crear_pose_v4(proyecto_tmp, "frontal_pulgar_02")).tipo == "acento"
    assert cargar_pose(crear_pose_v4(proyecto_tmp, "frontal_neutro_03")).tipo == "estado"
    assert cargar_pose(crear_pose_v4(proyecto_tmp, "frontal_libreta_04", tipo="acento")).tipo == "acento"


def test_gestos_con_tilde_y_vistas_con_guion_bajo_funcionan(proyecto_tmp):
    pose = cargar_pose(crear_pose_v4(proyecto_tmp, "tres_cuartos_der_señalar_01"))
    assert pose.gesto == "señalar" and pose.vista == "tres_cuartos_der"


def test_el_cuerpo_se_calibra_solo_con_la_cabeza_derivada_de_la_boca_a(proyecto_tmp):
    pose = cargar_pose(crear_pose_v4(proyecto_tmp))
    assert pose.anclas.cabeza.x == FORMAS["A"]["x"] and pose.anclas.cabeza.y < FORMAS["A"]["y"]


@pytest.mark.parametrize("nombre", ["explicar_01", "frontal_explicar", "frontal__01", "tres cuartos_x_01"])
def test_nombres_de_pose_invalidos_explican_la_nomenclatura(proyecto_tmp, nombre):
    carpeta = proyecto_tmp / "personajes" / "p" / "poses" / nombre
    carpeta.mkdir(parents=True)
    (carpeta / "config.yaml").write_text("version: 4\n", encoding="utf-8")
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(carpeta)
    assert "<vista>_<gesto>_<NN>" in str(exc.value)


def test_el_id_del_config_debe_coincidir_con_la_carpeta(proyecto_tmp):
    carpeta = crear_pose_v4(proyecto_tmp)
    cfg = yaml.safe_load((carpeta / "config.yaml").read_text(encoding="utf-8"))
    cfg["id"] = "frontal_neutro_01"
    (carpeta / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(carpeta)
    assert "no coincide" in str(exc.value)


def test_faltan_formas_de_boca_se_nombran(proyecto_tmp):
    incompletas = {k: v for k, v in FORMAS.items() if k not in ("C", "G")}
    carpeta = crear_pose_v4(proyecto_tmp, formas=incompletas)
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(carpeta)
    assert "C" in str(exc.value) and "G" in str(exc.value) and "calibr" in exc.value.sugerencia.lower()


def test_una_pose_sin_calibrar_pide_calibrarla(proyecto_tmp):
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(crear_pose_v4(proyecto_tmp, formas={}))
    assert "calibr" in str(exc.value).lower()


def test_tipo_invalido_se_rechaza(proyecto_tmp):
    with pytest.raises(AssetInvalido) as exc:
        cargar_pose(crear_pose_v4(proyecto_tmp, tipo="raro"))
    assert "estado" in str(exc.value) and "acento" in str(exc.value)


def test_el_config_v4_se_escribe_y_se_lee_sin_perder_nada(proyecto_tmp):
    formas = {v: {"x": 100.5 + i, "y": 90.0, "s": 0.236, "r": -3.1 if v == "D" else 0.0, "m": v == "H"}
              for i, v in enumerate(VISEMAS)}
    pose = cargar_pose(crear_pose_v4(proyecto_tmp, formas=formas, espejo=True, pelo=(160.0, 40.0)))
    assert pose.espejo is True and pose.pelo == (160.0, 40.0)
    assert pose.formas["D"].r == -3.1 and pose.formas["H"].m is True and pose.formas["A"].m is False
    assert pose.formas["B"].x == 101.5 and pose.formas["B"].s == 0.236


def test_las_poses_antiguas_p1_siguen_funcionando(proyecto_tmp):
    from src.biblioteca.placeholders import crear_pose_placeholder
    carpeta = proyecto_tmp / "personajes" / "p" / "poses" / "P1_demo"
    crear_pose_placeholder(carpeta, "P1", lienzo=(320, 180))
    pose = cargar_pose(carpeta)
    assert pose.id == "P1" and pose.formas is None and pose.vista == ""


# ---------------- reflejo: pose y forma se combinan (o exclusivo) ----------------
@pytest.mark.parametrize("espejo_pose, m_forma, esperado",
                         [(False, False, False), (True, False, True), (False, True, True), (True, True, False)])
def test_el_reflejo_de_la_pose_y_el_de_la_forma_se_combinan(proyecto_tmp, espejo_pose, m_forma, esperado):
    formas = {v: dict(FORMAS[v], m=(m_forma and v == "H")) for v in VISEMAS}
    pose = cargar_pose(crear_pose_v4(proyecto_tmp, formas=formas, espejo=espejo_pose))
    assert espejo_de_forma(pose, "H") is esperado
    otra = (espejo_pose)                                  # las demás formas solo siguen a la pose
    assert espejo_de_forma(pose, "A") is otra


# ---------------- validación (FR-061 con calibración por forma) ----------------
def test_las_bocas_pueden_tener_tamanos_distintos_cuando_hay_calibracion_por_forma(proyecto_tmp):
    pose = validar_pose(crear_pose_v4(proyecto_tmp))
    assert pose.formas is not None


def test_una_boca_faltante_se_nombra(proyecto_tmp):
    carpeta = crear_pose_v4(proyecto_tmp)
    (carpeta / "bocas" / "E.png").unlink()
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(carpeta)
    assert "E.png" in str(exc.value)


def test_el_parpadeo_no_exige_ojos_cerrados_en_poses_v4(proyecto_tmp):
    validar_pose(crear_pose_v4(proyecto_tmp))             # sin ojos_cerrados.png: no falla


def test_las_poses_de_una_vista_comparten_el_juego_de_bocas_con_bocas_de(proyecto_tmp):
    dueña = crear_pose_v4(proyecto_tmp, "tres_cuartos_der_neutro_01")
    otra = crear_pose_v4(proyecto_tmp, "tres_cuartos_der_explicar_01", con_bocas=False, bocas_de="tres_cuartos_der_neutro_01")
    pose = validar_pose(otra)
    from src.biblioteca.validacion import carpeta_fuente_bocas
    assert carpeta_fuente_bocas(pose) == dueña


def test_no_se_pueden_usar_bocas_de_otra_vista(proyecto_tmp):
    crear_pose_v4(proyecto_tmp, "frontal_neutro_01")
    tres_cuartos = crear_pose_v4(proyecto_tmp, "tres_cuartos_der_explicar_01", con_bocas=False, bocas_de="frontal_neutro_01")
    with pytest.raises(AssetInvalido) as exc:
        validar_pose(tres_cuartos)
    assert "vista" in str(exc.value).lower() and "tres_cuartos_der" in str(exc.value) and "frontal" in str(exc.value)


# ---------------- la capa de boca con calibración por forma (T096) ----------------
def _capa(pose):
    return BocaLayer(pose, AnclasEstaticas(pose), ventana_plano(pose, "PL1"), SALIDA)


def test_cada_forma_va_en_su_propio_centro_con_su_propia_escala(proyecto_tmp):
    pose = cargar_pose(crear_pose_v4(proyecto_tmp))
    capa = _capa(pose)
    esc = SALIDA[0] / LIENZO[0]
    for i, v in enumerate(VISEMAS):
        c = capa.renderizar(_ctx(v))
        f = pose.formas[v]
        ancho_nativo = 40 + 4 * i
        assert c.imagen.width == pytest.approx(ancho_nativo * f.s * esc, abs=1.5)
        assert c.x + c.imagen.width / 2 == pytest.approx(f.x * esc, abs=1.5)
        assert c.y + c.imagen.height / 2 == pytest.approx(f.y * esc, abs=1.5)


def test_cambiar_una_forma_no_altera_las_demas(proyecto_tmp):
    base = cargar_pose(crear_pose_v4(proyecto_tmp))
    formas = {v: dict(FORMAS[v]) for v in VISEMAS}
    formas["D"].update(x=170, y=110, s=1.0, r=12.0)
    tocada = cargar_pose(crear_pose_v4(proyecto_tmp, "tres_cuartos_der_explicar_01", formas=formas, con_bocas=False,
                                       bocas_de="tres_cuartos_der_neutro_01"))
    a, b = _capa(base), _capa(tocada)
    for v in VISEMAS:
        ra, rb = a.renderizar(_ctx(v)), b.renderizar(_ctx(v))
        igual = ra.imagen.tobytes() == rb.imagen.tobytes() and (ra.x, ra.y) == (rb.x, rb.y)
        assert igual is (v != "D")


def test_el_giro_de_la_forma_rota_su_sprite(proyecto_tmp):
    formas = {v: dict(FORMAS[v]) for v in VISEMAS}
    formas["C"]["r"] = 30.0
    recta, girada = _capa(cargar_pose(crear_pose_v4(proyecto_tmp))), _capa(cargar_pose(crear_pose_v4(
        proyecto_tmp, "tres_cuartos_der_explicar_01", formas=formas, con_bocas=False, bocas_de="tres_cuartos_der_neutro_01")))
    assert girada.renderizar(_ctx("C")).imagen.size != recta.renderizar(_ctx("C")).imagen.size


def test_el_giro_es_horario_como_en_los_calibradores(proyecto_tmp):
    """r positivo = sentido de las agujas del reloj: el borde derecho del sprite baja."""
    formas = {v: dict(FORMAS[v], s=3.0, r=20.0 if v == "D" else 0.0) for v in VISEMAS}
    pose = cargar_pose(crear_pose_v4(proyecto_tmp, formas=formas))
    img = _capa(pose).renderizar(_ctx("D")).imagen
    def centro_vertical_de_color(color, mitad):
        pts = [y for y in range(img.height) for x in range(mitad[0], mitad[1]) if img.getpixel((x, y))[3] > 200
               and img.getpixel((x, y))[:3] == color]
        return sum(pts) / len(pts)
    izq_y = centro_vertical_de_color((255, 0, 0), (0, img.width // 2))
    der_y = centro_vertical_de_color((0, 0, 255), (img.width // 2, img.width))
    assert der_y > izq_y


def test_el_reflejo_voltea_el_sprite_y_la_forma_lo_invierte_otra_vez(proyecto_tmp):
    def lado_izquierdo(pose):
        img = _capa(pose).renderizar(_ctx("D")).imagen
        return img.getpixel((2, img.height // 2))[:3]
    normal = cargar_pose(crear_pose_v4(proyecto_tmp))
    espejada = cargar_pose(crear_pose_v4(proyecto_tmp, "tres_cuartos_der_explicar_01", espejo=True, con_bocas=False,
                                         bocas_de="tres_cuartos_der_neutro_01"))
    formas_m = {v: dict(FORMAS[v], m=(v == "D")) for v in VISEMAS}
    anulada = cargar_pose(crear_pose_v4(proyecto_tmp, "tres_cuartos_der_pulgar_01", espejo=True, formas=formas_m,
                                        con_bocas=False, bocas_de="tres_cuartos_der_neutro_01"))
    assert lado_izquierdo(normal) == (255, 0, 0)          # rojo a la izquierda
    assert lado_izquierdo(espejada) == (0, 0, 255)        # reflejada: azul a la izquierda
    assert lado_izquierdo(anulada) == (255, 0, 0)         # pose reflejada + forma invertida = original


def test_la_boca_acompana_al_desplazamiento_de_alineacion(proyecto_tmp):
    pose = cargar_pose(crear_pose_v4(proyecto_tmp))
    sin = BocaLayer(pose, AnclasEstaticas(pose), ventana_plano(pose, "PL1"), SALIDA).renderizar(_ctx("D"))
    con = BocaLayer(pose, AnclasEstaticas(pose), ventana_plano(pose, "PL1"), SALIDA,
                    desplazamiento=(20.0, -10.0)).renderizar(_ctx("D"))
    esc = SALIDA[0] / LIENZO[0]
    # ±1 px: el redondeo de la posición del sprite (a la mitad más cercana) puede variar un píxel
    assert abs((con.x - sin.x) - 20.0 * esc) <= 1 and abs((con.y - sin.y) - (-10.0 * esc)) <= 1
