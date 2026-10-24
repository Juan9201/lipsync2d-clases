"""Seguimiento en vivo de una clase: etapas con inicio y fin en milisegundos, avance del render, y lectura para la interfaz."""
import json

import pytest

from src import progreso
from src.progreso import SeguimientoClase, con_seguimiento, leer_todos
from src.registro import etapa, obtener_logger


class Reloj:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


@pytest.fixture(autouse=True)
def sin_seguimiento_residual():
    progreso._actual = None
    yield
    progreso._actual = None


def _leer(raiz, clase):
    return json.loads((raiz / "logs" / "progreso" / f"{clase}.json").read_text(encoding="utf-8"))


def test_las_etapas_quedan_con_inicio_y_fin_en_milisegundos(tmp_path):
    r = Reloj()
    s = SeguimientoClase(tmp_path, "A1-M01-2", reloj=r)
    assert _leer(tmp_path, "A1-M01-2")["estado"] == "en_curso"
    s.empezar("voz"); r.avanzar(1.234); s.terminar("voz")
    s.empezar("rhubarb"); r.avanzar(0.5); s.terminar("rhubarb")
    s.cerrar("hecha")
    d = _leer(tmp_path, "A1-M01-2")
    assert d["estado"] == "hecha" and d["actual"] is None
    voz, rhu = d["etapas"]
    assert (voz["nombre"], voz["fin_ms"] - voz["inicio_ms"], voz["estado"]) == ("voz", 1234, "ok")
    assert rhu["inicio_ms"] == voz["fin_ms"] and rhu["fin_ms"] - rhu["inicio_ms"] == 500
    assert d["fin_ms"] - d["inicio_ms"] == 1734


def test_la_etapa_en_curso_figura_como_actual_hasta_que_termina(tmp_path):
    r = Reloj()
    s = SeguimientoClase(tmp_path, "c", reloj=r)
    s.empezar("capas")
    d = _leer(tmp_path, "c")
    assert d["actual"] == "capas" and d["etapas"][0]["fin_ms"] is None and d["etapas"][0]["estado"] == "en_curso"
    s.terminar("capas")
    assert _leer(tmp_path, "c")["actual"] is None


def test_el_registro_de_etapas_alimenta_al_seguimiento_y_un_error_lo_marca(tmp_path):
    log = obtener_logger("prueba_progreso")
    with con_seguimiento(tmp_path, "c", reloj=Reloj()):
        with etapa(log, "assets"):
            pass
        with pytest.raises(ValueError):
            with etapa(log, "rhubarb"):
                raise ValueError("falló")
    d = _leer(tmp_path, "c")
    assert [(e["nombre"], e["estado"]) for e in d["etapas"]] == [("assets", "ok"), ("rhubarb", "error")]
    assert d["estado"] == "hecha"                                              # el contexto salió sin excepción propia


def test_una_excepcion_que_sale_del_seguimiento_lo_cierra_como_error_con_el_mensaje(tmp_path):
    with pytest.raises(RuntimeError):
        with con_seguimiento(tmp_path, "c", reloj=Reloj()):
            raise RuntimeError("se cayó el TTS")
    d = _leer(tmp_path, "c")
    assert d["estado"] == "error" and "TTS" in d["error"]


def test_seguimientos_anidados_reutilizan_el_externo_y_solo_el_externo_cierra(tmp_path):
    with con_seguimiento(tmp_path, "c", reloj=Reloj()) as externo:
        with con_seguimiento(tmp_path, "c") as interno:
            assert interno is externo
        assert _leer(tmp_path, "c")["estado"] == "en_curso"
    assert _leer(tmp_path, "c")["estado"] == "hecha"


def test_el_avance_se_limita_para_no_escribir_el_archivo_miles_de_veces(tmp_path):
    r = Reloj()
    s = SeguimientoClase(tmp_path, "c", reloj=r)
    base = s.escrituras
    for n in range(1000):
        s.avance(n, 1000)                                                      # el reloj no avanza: casi todo se descarta
    assert s.escrituras - base <= 3
    r.avanzar(1.0)
    s.avance(1000, 1000)                                                       # el último cuadro siempre se escribe
    d = _leer(tmp_path, "c")
    assert d["n"] == 1000 and d["total"] == 1000 and d["fraccion"] == 1.0


def test_avance_sin_seguimiento_activo_no_hace_nada(tmp_path):
    progreso.avance(5, 10)                                                     # no debe fallar
    assert not (tmp_path / "logs").exists()


def test_leer_todos_ordena_marca_sin_senal_e_ignora_archivos_rotos(tmp_path):
    r = Reloj(1000.0)
    a = SeguimientoClase(tmp_path, "vieja", reloj=r)
    r.avanzar(500)
    b = SeguimientoClase(tmp_path, "nueva", reloj=r)
    (tmp_path / "logs" / "progreso" / "rota.json").write_text("{no es json", encoding="utf-8")
    r.avanzar(300)                                                             # «vieja» lleva 800 s sin actualizar; «nueva», 300 s
    lista = leer_todos(tmp_path, ahora_ms=int(r() * 1000), caducidad_s=600)
    assert [c["clase"] for c in lista] == ["nueva", "vieja"]
    assert {c["clase"]: c["estado"] for c in lista} == {"nueva": "en_curso", "vieja": "sin_senal"}
    b.cerrar("hecha")
    assert {c["clase"]: c["estado"] for c in leer_todos(tmp_path, ahora_ms=int(r() * 1000), caducidad_s=600)}["nueva"] == "hecha"
