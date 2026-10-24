"""Un escenario cuyo fondo es casi todo transparente (p. ej. la capa delantera subida como si fuera un fondo) se vería negro:
el reparto automático de escenarios del lote no debe elegirlo, y la interfaz debe avisarlo."""
from types import SimpleNamespace

import pytest
from PIL import Image

from src.escena.config import fraccion_transparente
from src.lote.trabajadores import _escenario_de
from src.ui import logica


def _fondo(carpeta, transparente_pct):
    carpeta.mkdir(parents=True)
    im = Image.new("RGBA", (100, 100), (200, 100, 50, 255))
    n = int(100 * transparente_pct / 100)
    for y in range(n):
        for x in range(100):
            im.putpixel((x, y), (0, 0, 0, 0))
    im.save(carpeta / "fondo.png")


@pytest.fixture
def proyecto(tmp_path):
    _fondo(tmp_path / "escenarios" / "E1_aula", 0)
    _fondo(tmp_path / "escenarios" / "E2_solo_frente", 70)           # una capa delantera subida como fondo
    _fondo(tmp_path / "escenarios" / "E3_calle", 5)
    return tmp_path


def test_fraccion_transparente_mide_la_parte_sin_imagen(proyecto):
    assert fraccion_transparente(proyecto / "escenarios" / "E1_aula" / "fondo.png") == 0.0
    assert 0.65 <= fraccion_transparente(proyecto / "escenarios" / "E2_solo_frente" / "fondo.png") <= 0.75
    assert fraccion_transparente(proyecto / "escenarios" / "E1_aula" / "no_existe.png") == 0.0
    assert fraccion_transparente(proyecto / "escenarios" / "fondo.mp4") == 0.0                  # un video no se mide


def test_el_reparto_automatico_nunca_elige_un_fondo_casi_transparente(proyecto):
    elegidos = {_escenario_de(SimpleNamespace(escenarios="", id=f"A1-M{m:02d}-{p}"), proyecto) for m in range(1, 41) for p in (2, 3, 4)}
    assert elegidos == {"E1", "E3"}                                                           # reparte entre los válidos; E2 jamás


def test_si_la_clase_pide_un_escenario_se_respeta_aunque_sea_transparente(proyecto):
    assert _escenario_de(SimpleNamespace(escenarios="E2", id="A1-M01-4"), proyecto) == "E2"


def test_si_todos_son_casi_transparentes_no_hay_escenario_automatico(tmp_path):
    _fondo(tmp_path / "escenarios" / "E1_solo_frente", 80)
    assert _escenario_de(SimpleNamespace(escenarios="", id="A1-M01-4"), tmp_path) is None


def test_la_interfaz_informa_cuanto_tiene_de_transparente_cada_escenario(proyecto):
    por_id = {e["id"]: e for e in logica.escenarios_disponibles(proyecto)}
    assert por_id["E1"]["transparente"] == 0.0 and por_id["E2"]["transparente"] > 0.6
