"""FR-012: el análisis de visemas no recibe ninguna marca entre corchetes."""
from src.guion import limpiar_para_analisis


def test_quita_todas_las_marcas_entre_corchetes():
    texto = "Hola [short pause] a todos. [pose:P3] Hoy [giggle] vemos más."
    assert limpiar_para_analisis(texto) == "Hola a todos. Hoy vemos más."


def test_conserva_acentos_y_normaliza_espacios_y_saltos():
    assert limpiar_para_analisis("Qué  tal\n\n¿Cómo   estás?") == "Qué tal ¿Cómo estás?"


def test_vacio_o_solo_marcas():
    assert limpiar_para_analisis("") == ""
    assert limpiar_para_analisis("[pose:P1] [toma:E1,P1,PL2]") == ""
