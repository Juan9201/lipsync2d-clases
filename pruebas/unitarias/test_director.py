"""T068, T069, T101 (FR-044 a FR-046, FR-090 a FR-094): el director elige las tomas — pose, plano de la cámara virtual y
momento del corte — con reglas, reproducibles con la semilla, y las reglas se ajustan en un archivo."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.director import REGLAS_DEFECTO, cargar_reglas, dirigir
from src.errores import ErrorAccionable
from src.timeline import Visema

FPS = 25
N = 280 * FPS                                  # una clase de ~5 min
PLANOS = ["PL1", "PL2", "PL3", "PL4", "PL5", "PL6"]


def _pose(id_, tipo="estado"):
    vista, gesto, nn = id_.rsplit("_", 2)
    return SimpleNamespace(id=id_, vista=vista, gesto=gesto, tipo=tipo, variante=int(nn))


POSES = [_pose("frontal_neutro_01"), _pose("frontal_neutro_02"), _pose("frontal_explicar_01"),
         _pose("frontal_libreta_01"), _pose("frontal_pregunta_01"), _pose("tres_cuartos_der_neutro_01"),
         _pose("tres_cuartos_der_explicar_01"),
         _pose("frontal_pulgar_01", "acento"), _pose("frontal_señalar_01", "acento"),
         _pose("tres_cuartos_der_pulgar_01", "acento")]
SOLO_ESTADOS = [p for p in POSES if p.tipo == "estado"]


def _visemas(n=N, cada_s=3.5, pausa_f=8):
    """Voz con una pausa (X) cada `cada_s` segundos."""
    v, f = [], 0
    while f < n:
        habla = min(round(cada_s * FPS) - pausa_f, n - f)
        v.append(Visema(f, f + habla, "D"))
        f += habla
        if f < n:
            v.append(Visema(f, min(f + pausa_f, n), "X"))
            f = min(f + pausa_f, n)
    return v


def _dirigir(poses=POSES, semilla=1, reglas=None, n=N, **kw):
    return dirigir(poses, _visemas(n), n, FPS, "E1", semilla, cargar_reglas(None, reglas), **kw)


def _idx(plano, permitidos):
    return permitidos.index(plano)


# ---------------- estructura de las tomas ----------------
def test_las_tomas_empiezan_en_cero_y_son_crecientes_y_dentro_del_video():
    tomas = _dirigir()
    assert tomas[0].f0 == 0 and tomas[0].escenario == "E1"
    assert all(b.f0 > a.f0 for a, b in zip(tomas, tomas[1:])) and tomas[-1].f0 < N


def test_la_duracion_de_cada_toma_respeta_el_minimo_y_los_cortes_caen_en_pausas():
    tomas = _dirigir(reglas={"acentos": {"activo": False}})
    pausas = {v.f0 for v in _visemas() if v.v == "X"}
    cortes = [t.f0 for t in tomas[1:]]
    assert sum(c in pausas for c in cortes) >= 0.9 * len(cortes)                      # FR-054: en la pausa más cercana
    largos = [(b.f0 - a.f0) / FPS for a, b in zip(tomas, tomas[1:])]
    assert min(largos) >= 6 - 0.01 and max(largos) <= 20 + 2 + 0.5                      # 6 a 20 s (+ tolerancia de pausa)


def test_sin_pausas_corta_en_el_punto_exacto_y_no_falla():
    tomas = dirigir(POSES, [Visema(0, N, "D")], N, FPS, "E1", 1, cargar_reglas(None))
    assert len(tomas) > 5


# ---------------- poses y planos ----------------
def test_no_repite_la_misma_pose_dos_tomas_seguidas_cuando_cambia_de_pose():
    tomas = _dirigir()
    for a, b in zip(tomas, tomas[1:]):
        if a.pose != b.pose:
            assert a.plano == b.plano                          # un solo elemento a la vez (cambia pose o cambia plano)
        else:
            assert a.plano != b.plano                          # misma pose: el corte es un cambio de plano


def test_el_plano_cambia_de_un_paso_y_solo_usa_los_permitidos():
    tomas = _dirigir(reglas={"planos": {"paso_maximo": 1}})
    permitidos = REGLAS_DEFECTO["planos"]["permitidos"]
    assert {t.plano for t in tomas} <= set(permitidos)
    assert len({t.plano for t in tomas}) >= 3                  # la cámara realmente varía
    for a, b in zip(tomas, tomas[1:]):
        assert abs(_idx(a.plano, permitidos) - _idx(b.plano, permitidos)) <= 1


def test_el_plano_inicial_es_el_de_las_reglas_o_el_indicado():
    assert _dirigir()[0].plano == REGLAS_DEFECTO["planos"]["inicial"]
    assert _dirigir(plano_inicial="PL5")[0].plano == "PL5"


def test_con_una_sola_pose_la_camara_igual_varia_el_plano():
    tomas = _dirigir(poses=[POSES[0]])
    assert {t.pose for t in tomas} == {POSES[0].id}
    assert len({t.plano for t in tomas}) >= 3


def test_hay_variedad_de_poses_de_reposo_y_de_vistas():
    tomas = _dirigir(reglas={"acentos": {"activo": False}})
    usadas = {t.pose for t in tomas}
    assert len(usadas) >= 5                                    # de las 7 poses de reposo
    assert {"frontal", "tres_cuartos_der"} <= {p.vista for p in SOLO_ESTADOS if p.id in usadas}


def test_las_restricciones_del_escenario_nunca_se_rompen():
    def admite(pose, plano):
        return plano in ("PL3", "PL4") and not pose.startswith("tres_cuartos")
    tomas = _dirigir(admite=admite)
    assert all(admite(t.pose, t.plano) for t in tomas)


def test_si_el_escenario_no_admite_nada_se_avisa_con_una_salida_clara():
    with pytest.raises(ErrorAccionable) as exc:
        _dirigir(admite=lambda pose, plano: False)
    assert "escenario" in str(exc.value).lower()


# ---------------- reproducibilidad ----------------
def test_misma_semilla_mismas_tomas_y_otra_semilla_distintas():
    assert _dirigir(semilla=5) == _dirigir(semilla=5)
    assert _dirigir(semilla=5) != _dirigir(semilla=6)


# ---------------- reposo, acentos y mezcla (FR-044, FR-045) ----------------
def test_los_acentos_duran_de_3_a_6_segundos_y_vuelven_al_reposo():
    tomas = _dirigir(reglas={"acentos": {"probabilidad": 1.0}})
    por_id = {p.id: p for p in POSES}
    acentos = [i for i, t in enumerate(tomas[:-1]) if por_id[t.pose].tipo == "acento"]
    assert acentos, "con probabilidad 1 debería haber acentos"
    for i in acentos:
        dur = (tomas[i + 1].f0 - tomas[i].f0) / FPS
        assert 3 - 0.05 <= dur <= 6 + 0.05, dur
        assert por_id[tomas[i + 1].pose].tipo == "estado"                              # vuelve solo al reposo


def test_no_hay_mas_de_un_acento_cada_20_segundos():
    tomas = _dirigir(reglas={"acentos": {"probabilidad": 1.0}})
    por_id = {p.id: p for p in POSES}
    inicios = [t.f0 for t in tomas if por_id[t.pose].tipo == "acento"]
    assert all((b - a) / FPS >= 20 - 0.01 for a, b in zip(inicios, inicios[1:]))


def test_los_acentos_se_pueden_apagar_y_no_aparecen():
    por_id = {p.id: p for p in POSES}
    assert not any(por_id[t.pose].tipo == "acento" for t in _dirigir(reglas={"acentos": {"activo": False}}))


def test_una_clase_sin_poses_de_acento_usa_solo_reposo():
    assert {t.pose for t in _dirigir(poses=SOLO_ESTADOS)} <= {p.id for p in SOLO_ESTADOS}


def test_cambiar_de_pose_mezcla_2_frames_y_cambiar_de_plano_es_un_corte_seco():
    tomas = _dirigir()
    for a, b in zip(tomas, tomas[1:]):
        assert b.mezcla == (2 if a.pose != b.pose else 0)
    assert tomas[0].mezcla == 0


def test_la_mezcla_se_puede_apagar():
    assert all(t.mezcla == 0 for t in _dirigir(reglas={"reposo": {"mezcla_frames": 0}}))


# ---------------- reglas en un archivo (T069, FR-094, FR-046) ----------------
def test_las_reglas_por_defecto_son_validas_y_estan_completas():
    r = cargar_reglas(None)
    assert r["toma_s"] == [6, 20] and r["acentos"]["duracion_s"] == [3, 6] and r["acentos"]["separacion_min_s"] == 20
    assert r["reposo"]["mezcla_frames"] == 2 and r["planos"]["paso_maximo"] == 2 and r["planos"]["max_mismo_s"] == 25


def test_el_archivo_de_reglas_cambia_el_comportamiento_sin_tocar_el_codigo(tmp_path):
    base = len(_dirigir())
    ruta = tmp_path / "reglas.yaml"
    ruta.write_text(yaml.safe_dump({"toma_s": [40, 60]}), encoding="utf-8")
    pocas = dirigir(POSES, _visemas(), N, FPS, "E1", 1, cargar_reglas(ruta))
    assert len(pocas) < base / 2
    ruta.write_text(yaml.safe_dump({"planos": {"permitidos": ["PL4"], "inicial": "PL4"}}), encoding="utf-8")
    assert {t.plano for t in dirigir(POSES, _visemas(), N, FPS, "E1", 1, cargar_reglas(ruta))} == {"PL4"}
    ruta.write_text(yaml.safe_dump({"cambio": {"prob_plano": 0.0}, "planos": {"max_mismo_s": 0}}), encoding="utf-8")
    solo_poses = dirigir(POSES, _visemas(), N, FPS, "E1", 1, cargar_reglas(ruta))
    assert len({t.plano for t in solo_poses}) == 1


def test_un_valor_que_no_se_indica_conserva_el_de_por_defecto(tmp_path):
    ruta = tmp_path / "reglas.yaml"
    ruta.write_text(yaml.safe_dump({"acentos": {"probabilidad": 0.9}}), encoding="utf-8")
    r = cargar_reglas(ruta)
    assert r["acentos"]["probabilidad"] == 0.9 and r["acentos"]["duracion_s"] == [3, 6] and r["toma_s"] == [6, 20]


@pytest.mark.parametrize("cambio, texto", [
    ({"toma_s": [20, 6]}, "toma_s"),
    ({"planos": {"permitidos": ["PL9"]}}, "PL9"),
    ({"acentos": {"duracion_s": [6, 3]}}, "duracion_s"),
    ({"cambio": {"prob_plano": 1.5}}, "prob_plano"),
    ({"reposo": {"mezcla_frames": -1}}, "mezcla_frames"),
    ({"planos": {"inicial": "PL1", "permitidos": ["PL3"]}}, "inicial"),
])
def test_reglas_invalidas_se_rechazan_nombrando_el_valor(tmp_path, cambio, texto):
    ruta = tmp_path / "reglas.yaml"
    ruta.write_text(yaml.safe_dump(cambio), encoding="utf-8")
    with pytest.raises(ErrorAccionable) as exc:
        cargar_reglas(ruta)
    assert texto in str(exc.value)


def test_un_yaml_roto_o_inexistente_da_un_error_claro(tmp_path):
    roto = tmp_path / "roto.yaml"
    roto.write_text("toma_s: [1, 2\n", encoding="utf-8")
    with pytest.raises(ErrorAccionable):
        cargar_reglas(roto)
    with pytest.raises(ErrorAccionable):
        cargar_reglas(tmp_path / "no_existe.yaml")


def test_el_registro_explica_cada_decision():
    lineas = []
    _dirigir(registro=lineas.append)
    assert lineas and all("toma" in l.lower() for l in lineas)
    assert any("plano" in l for l in lineas) and any("pose" in l for l in lineas)


def test_el_archivo_reglas_director_del_proyecto_es_valido_y_coincide_con_los_valores_por_defecto():
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[2] / "reglas_director.yaml"
    assert cargar_reglas(ruta) == cargar_reglas(None)


def test_la_camara_evita_los_vaivenes_entre_dos_planos():
    def vaivenes(evitar):
        total = aba = 0
        for semilla in range(30):
            t = _dirigir(semilla=semilla, reglas={"planos": {"evitar_volver": evitar}, "cambio": {"prob_plano": 0.9},
                                                  "acentos": {"activo": False}})
            seguidos = [x.plano for a, x in zip(t, t[1:]) if a.pose == x.pose]
            total += max(len(seguidos) - 1, 0)
            aba += sum(1 for p, q, r in zip(seguidos, seguidos[1:], seguidos[2:]) if p == r)
        return aba / total
    assert vaivenes(0.2) < 0.7 * vaivenes(1.0)


def test_evitar_volver_fuera_de_rango_se_rechaza(tmp_path):
    ruta = tmp_path / "r.yaml"
    ruta.write_text(yaml.safe_dump({"planos": {"evitar_volver": 2}}), encoding="utf-8")
    with pytest.raises(ErrorAccionable) as exc:
        cargar_reglas(ruta)
    assert "evitar_volver" in str(exc.value)


def _planos_de(tomas, n_frames, fps):
    """Segundos que cada plano estuvo en pantalla y el tramo continuo más largo en un mismo plano."""
    tiempo, seguido, ini, prev = {}, 0, 0, None
    for a, b in zip(tomas, [*tomas[1:], type("F", (), {"f0": n_frames})()]):
        tiempo[a.plano] = tiempo.get(a.plano, 0) + (b.f0 - a.f0) / fps
    for t in tomas:
        if t.plano != prev:
            if prev is not None:
                seguido = max(seguido, (t.f0 - ini) / fps)
            prev, ini = t.plano, t.f0
    return tiempo, max(seguido, (n_frames - ini) / fps)


def test_max_mismo_s_obliga_a_cambiar_de_plano_y_las_reglas_del_proyecto_usan_los_cinco():
    from types import SimpleNamespace
    fps, n = 25, 300 * 25
    poses = [SimpleNamespace(id="frontal_neutro_01", vista="frontal", gesto="neutro", tipo="estado", mirada="camara", cuenta=0),
             SimpleNamespace(id="frontal_explicar_01", vista="frontal", gesto="explicar", tipo="estado", mirada="camara", cuenta=0)]
    vis = [v for i in range(0, n, 55) for v in (Visema(i, i + 42, "C"), Visema(i + 42, i + 55, "X"))]
    base = {"cambio": {"prob_plano": 0.0}}                        # sin cambios de plano al azar: solo el límite puede cambiarlos
    sin = [_planos_de(dirigir(poses, vis, n, fps, "E2", s, cargar_reglas(None, {**base, "planos": {"max_mismo_s": 0}})), n, fps)[1] for s in range(6)]
    con = [_planos_de(dirigir(poses, vis, n, fps, "E2", s, cargar_reglas(None, {**base, "planos": {"max_mismo_s": 25}})), n, fps)[1] for s in range(6)]
    assert max(sin) > 100 and max(con) < 25 + 20 + 1             # el máximo es el límite más lo que tarda el corte siguiente (toma_s ≤ 20)
    proyecto = cargar_reglas(Path(__file__).resolve().parents[2] / "reglas_director.yaml")
    usados = set()
    for s in range(12):
        usados |= set(_planos_de(dirigir(poses, vis, n, fps, "E2", s, proyecto), n, fps)[0])
    assert usados == {"PL1", "PL2", "PL3", "PL4", "PL5"}


def test_max_mismo_s_invalido_se_rechaza():
    with pytest.raises(ErrorAccionable):
        cargar_reglas(None, {"planos": {"max_mismo_s": -3}})
