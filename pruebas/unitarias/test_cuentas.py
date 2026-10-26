"""Cuando el guion cuenta («uno, dos, tres» / «first, second, third») el director muestra la pose con ese número de dedos, a tiempo."""
from types import SimpleNamespace

import pytest

from src.director import cargar_reglas, dirigir
from src.lipsync import Cue
from src.palabras import detectar_cuentas, tiempos_de_palabras
from src.timeline import Visema

FPS = 25


def _voz(duracion, pausas=()):
    """Cues de una voz continua con pausas (X) en los instantes dados."""
    cues, t = [], 0.0
    for a, b in sorted(pausas) + [(duracion, duracion)]:
        if a > t:
            cues.append(Cue(t, a, "C"))
        if b > a:
            cues.append(Cue(a, b, "X"))
        t = b
    return cues


# ---------------------------------------------------------------- tiempos de las palabras
def test_las_palabras_se_reparten_por_sus_silabas_y_se_anclan_a_las_pausas():
    texto = "Hello there. " + "word " * 17 + "word. Last one here."
    pal = tiempos_de_palabras(texto, _voz(10.0, [(1.0, 1.3), (8.0, 8.4)]), 10.0)
    assert len(pal) == 2 + 18 + 3
    assert pal[1].t1 <= 1.05 and pal[2].t0 >= 1.25            # «there.» acaba en la primera pausa; «word» empieza tras ella
    assert pal[-3].t0 >= 8.35                                  # «Last» arranca después de la segunda
    assert all(a.t1 <= b.t0 + 1e-6 for a, b in zip(pal, pal[1:]))


def test_sin_pausas_utilizables_se_reparte_proporcionalmente():
    pal = tiempos_de_palabras("uno dos tres cuatro", _voz(8.0), 8.0)
    assert pal[0].t0 == pytest.approx(0.0) and pal[-1].t1 == pytest.approx(8.0)


# ---------------------------------------------------------------- detección
def _pal(texto):
    return tiempos_de_palabras(texto, _voz(60.0), 60.0)


@pytest.mark.parametrize("texto,esperado", [
    ("You need three pieces. First you need the subject. Second you need the verb. Third add the object.", ["First", "Second", "Third"]),
    ("Hay dos reglas. Primero, usa el verbo. Segundo, añade el sujeto.", ["Primero", "Segundo"]),
    ("Count with me: one, two, three, four.", ["one", "two", "three", "four"]),
    ("Step one is the greeting. Step two is the name.", ["one", "two"]),
    ("Repite: 1, 2, 3 y ya.", ["1", "2", "3"])])
def test_detecta_cuentas_en_ingles_y_en_espanol(texto, esperado):
    seqs = detectar_cuentas(texto, _pal(texto))
    assert [i.palabra for i in seqs[0]] == esperado and [i.n for i in seqs[0]] == list(range(1, len(esperado) + 1))


@pytest.mark.parametrize("texto", [
    "Wait one second. It takes two minutes.",
    "We can count one by one. Maybe you have three books and two pens.",
    "one week is not long enough. Then two days later we practice again.",
    "Second, you add the verb. Third, the object.",                    # no empieza en 1
    "The first rule is easy. The second is harder.",                   # «first» no abre cláusula: es un adjetivo
    "Hello and welcome to the class."])
def test_no_confunde_numeros_sueltos_con_una_cuenta(texto):
    assert detectar_cuentas(texto, _pal(texto)) == []


# ---------------------------------------------------------------- director
def _pose(id, **kw):
    base = dict(id=id, vista="frontal", gesto="neutro", tipo="estado", mirada="camara", cuenta=0)
    base.update(kw)
    return SimpleNamespace(**base)


POSES = [_pose("frontal_neutro_01"), _pose("frontal_explicar_01"),
         _pose("frontal_contar_01", gesto="contar", tipo="acento", cuenta=3),
         _pose("frontal_contar_03", gesto="contar", tipo="acento", cuenta=1),
         _pose("frontal_contar_04", gesto="contar", tipo="acento", cuenta=2)]
N = 60 * FPS
VIS = [Visema(i, i + 20, "C") for i in range(0, N, 40)] + [Visema(i + 20, i + 40, "X") for i in range(0, N - 40, 40)]
CUENTA = [[(1, 20 * FPS, 21 * FPS), (2, 24 * FPS, 25 * FPS), (3, 28 * FPS, 29 * FPS)]]


def _pose_en(tomas, f):
    return [t for t in tomas if t.f0 <= f][-1].pose


def test_las_poses_de_contar_nunca_salen_al_azar():
    for semilla in range(12):
        tomas = dirigir(POSES, VIS, N, FPS, "E2", semilla)
        assert not any("contar" in t.pose for t in tomas)


def test_cada_numero_muestra_sus_dedos_justo_cuando_se_dice():
    reglas = cargar_reglas(None)
    tomas = dirigir(POSES, VIS, N, FPS, "E2", 3, reglas, cuentas=CUENTA)
    a = reglas["cuentas"]["anticipo_s"]
    assert _pose_en(tomas, round(20.5 * FPS)) == "frontal_contar_03"
    assert _pose_en(tomas, round(24.5 * FPS)) == "frontal_contar_04"
    assert _pose_en(tomas, round(28.5 * FPS)) == "frontal_contar_01"
    assert _pose_en(tomas, round((20 - a - 0.3) * FPS)) not in {"frontal_contar_03", "frontal_contar_04", "frontal_contar_01"}
    assert _pose_en(tomas, 40 * FPS) not in {"frontal_contar_03", "frontal_contar_04", "frontal_contar_01"}     # y después vuelve a lo normal


def test_el_gesto_no_dura_mas_del_tope_ni_se_pisan_los_numeros_cercanos():
    seq = [[(1, 20 * FPS, 21 * FPS), (2, 22 * FPS, 23 * FPS), (3, 40 * FPS, 41 * FPS)]]
    tomas = dirigir(POSES, VIS, N, FPS, "E2", 5, cuentas=seq)
    assert _pose_en(tomas, round(21.5 * FPS)) == "frontal_contar_03"          # mantiene el 1 hasta que llega el 2
    assert _pose_en(tomas, round(22.5 * FPS)) == "frontal_contar_04"
    assert _pose_en(tomas, 30 * FPS) not in {"frontal_contar_04", "frontal_contar_03"}                           # el 2 no se queda 17 s


def test_con_las_cuentas_desactivadas_o_sin_poses_de_contar_no_cambia_nada():
    base = dirigir(POSES, VIS, N, FPS, "E2", 7)
    assert dirigir(POSES, VIS, N, FPS, "E2", 7, cuentas=CUENTA) != base
    assert dirigir(POSES, VIS, N, FPS, "E2", 7, cargar_reglas(None, {"cuentas": {"activo": False}}), cuentas=CUENTA) == base
    sin = [p for p in POSES if not p.cuenta]
    assert dirigir(sin, VIS, N, FPS, "E2", 7, cuentas=CUENTA) == dirigir(sin, VIS, N, FPS, "E2", 7)
