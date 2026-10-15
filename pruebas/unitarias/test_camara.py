"""FR-053 (base): ventana de recorte de cada plano como cámara virtual."""
import pytest
import yaml

from src.biblioteca.modelos import cargar_pose
from src.biblioteca.placeholders import crear_pose_placeholder
from src.layers.camara import ventana_plano


@pytest.fixture
def pose(proyecto_tmp):
    carpeta = proyecto_tmp / "personajes" / "p" / "poses" / "P1_x"
    crear_pose_placeholder(carpeta, "P1", lienzo=(1920, 1080))
    return cargar_pose(carpeta)


def test_pl1_es_todo_el_lienzo(pose):
    v = ventana_plano(pose, "PL1")
    assert (v.x0, v.y0) == (0, 0) and v.w == pytest.approx(1920) and v.h == pytest.approx(1080)
    assert v.escala(1280) == pytest.approx(1280 / 1920)


def test_pl4_tiene_el_alto_relativo_y_conserva_16_9(pose):
    v = ventana_plano(pose, "PL4")
    assert v.h == pytest.approx(0.42 * 1080)
    assert v.w / v.h == pytest.approx(16 / 9)
    assert 0 <= v.x0 and v.x0 + v.w <= 1920 + 1e-6
    assert 0 <= v.y0 and v.y0 + v.h <= 1080 + 1e-6


def test_la_cabeza_queda_dentro_de_la_ventana(pose):
    for plano in ("PL2", "PL3", "PL4", "PL5", "PL6"):
        v = ventana_plano(pose, plano)
        c = pose.anclas.cabeza
        assert v.x0 <= c.x <= v.x0 + v.w, plano
        assert v.y0 <= c.y <= v.y0 + v.h, plano


def test_planos_mas_cerrados_son_ventanas_mas_pequenas(pose):
    altos = [ventana_plano(pose, f"PL{i}").h for i in range(1, 7)]
    assert altos == sorted(altos, reverse=True)


def test_plano_desconocido(pose):
    with pytest.raises(KeyError):
        ventana_plano(pose, "PL9")
