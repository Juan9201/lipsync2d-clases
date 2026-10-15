"""FR-022, NFR-004: invariantes de la línea de tiempo (contrato linea-de-tiempo.md)."""
import pytest

from src.errores import ErrorAccionable
from src.timeline import LineaDeTiempo, Parpadeo, Toma, Visema, semilla_de_clase


def _base(**kw):
    datos = dict(
        fps=25, n_frames=100, semilla=1,
        visemas=[Visema(0, 40, "X"), Visema(40, 43, "D"), Visema(43, 100, "B")],
        tomas=[Toma(0, "E1", "P1", "PL2")],
        parpadeos=[Parpadeo(60, 4)],
    )
    datos.update(kw)
    return LineaDeTiempo(**datos)


def test_linea_valida_no_lanza():
    _base().validar()


def test_consulta_por_frame():
    lt = _base()
    assert lt.visema_en(0) == "X" and lt.visema_en(39) == "X"
    assert lt.visema_en(40) == "D" and lt.visema_en(99) == "B"
    assert lt.toma_en(50).plano == "PL2"
    assert lt.parpadeando(60) and lt.parpadeando(63) and not lt.parpadeando(64)


def test_huecos_en_visemas():
    with pytest.raises(ErrorAccionable):
        _base(visemas=[Visema(0, 40, "X"), Visema(41, 100, "B")]).validar()


def test_no_cubre_todos_los_frames():
    with pytest.raises(ErrorAccionable):
        _base(visemas=[Visema(0, 90, "X")]).validar()


def test_visema_invalido():
    with pytest.raises(ErrorAccionable):
        _base(visemas=[Visema(0, 100, "Z")]).validar()


def test_visema_corto_solo_se_permite_para_A():
    with pytest.raises(ErrorAccionable):
        _base(visemas=[Visema(0, 50, "X"), Visema(50, 51, "D"), Visema(51, 100, "B")]).validar()
    _base(visemas=[Visema(0, 50, "X"), Visema(50, 51, "A"), Visema(51, 100, "B")]).validar()


def test_la_primera_toma_empieza_en_cero_y_son_crecientes():
    with pytest.raises(ErrorAccionable):
        _base(tomas=[Toma(5, "E1", "P1", "PL2")]).validar()
    with pytest.raises(ErrorAccionable):
        _base(tomas=[Toma(0, "E1", "P1", "PL2"), Toma(30, "E1", "P1", "PL3"),
                     Toma(30, "E1", "P2", "PL3")]).validar()


def test_serializacion_json_ida_y_vuelta():
    lt = _base()
    assert LineaDeTiempo.desde_json(lt.a_json()) == lt


def test_semilla_de_clase_es_determinista_y_distinta():
    assert semilla_de_clase("clase_0001") == semilla_de_clase("clase_0001")
    assert semilla_de_clase("clase_0001") != semilla_de_clase("clase_0002")
    assert semilla_de_clase("x", base=5) != semilla_de_clase("x", base=6)


def test_parpadeos_con_duracion_o_separacion_fuera_de_rango_se_rechazan():
    with pytest.raises(ErrorAccionable):
        _base(parpadeos=[Parpadeo(60, 9)]).validar()                       # dura más de 5 frames
    with pytest.raises(ErrorAccionable):
        _base(parpadeos=[Parpadeo(10, 4), Parpadeo(20, 4)]).validar()      # separados menos de 2 s
    _base(parpadeos=[Parpadeo(10, 4), Parpadeo(80, 3)]).validar()


def test_parpadeando_con_muchos_parpadeos_usa_consulta_rapida():
    lt = _base(n_frames=1000, visemas=[Visema(0, 1000, "B")],
               parpadeos=[Parpadeo(60 + 70 * i, 4) for i in range(13)])
    assert lt.parpadeando(60 + 70 * 12 + 3) and not lt.parpadeando(60 + 70 * 12 + 4)
