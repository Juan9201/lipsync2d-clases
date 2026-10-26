"""Importación de los guiones generados en Drive (un .txt por clase): limpieza del texto, nombres de archivo, idioma por nivel,
solo las clases de IA, y que repetir la importación no duplique ni pise lo que el usuario ya ajustó."""
import json

import pytest

from src.errores import ErrorAccionable
from src.guiones_drive import IDIOMA_POR_NIVEL, escanear, importar_carpeta, leer_nombre, limpiar_guion
from src.ui import logica

RAYA = "-" * 49


def _bloque(titulo, texto):
    return f"{RAYA}\n{titulo}\n{RAYA}\n{texto}\n"


def _guion(palabras=800, hook=None, titulos=True):
    """Seis secciones de ~palabras/6 palabras cada una, con las marcas que deja el generador."""
    por = max(1, palabras // 6)
    nombres = ["The Definition and Purpose", "The Spanish Equivalent", "Common Mistakes", "Practice Phrases",
               "Contexts and Examples of Use", "Precautions for Listening and Speaking"]
    cuerpo = [(" ".join(f"s{i}p{k}" for k in range(por)) + ".") for i in range(6)]
    partes = ([hook + "\n\n"] if hook else []) + [(_bloque(n, c) if titulos else c + "\n") + "\n" for n, c in zip(nombres, cuerpo)]
    return "".join(partes)


# ---------------------------------------------------------------- limpieza
def test_limpiar_quita_titulos_rayas_y_marcas_y_conserva_el_orden():
    t = (f"{RAYA}\nThe Definition and Purpose\n{RAYA}\nPrimero **importante**.\n\n"
         f"{RAYA}\nThe Spanish Equivalent\n{RAYA}\n# Segundo [Text] párrafo.\n")
    limpio = limpiar_guion(t)
    assert limpio == "Primero importante.\n\nSegundo párrafo."


def test_limpiar_sirve_con_titulos_desfasados_o_ausentes():
    # el modelo a veces pone cada título una sección más abajo, deja el último vacío o se salta el primero
    t = ("Intro sin título.\n\n" + _bloque("The Definition and Purpose", "Segunda.") + "\n" +
         _bloque("The Spanish Equivalent", "Tercera.") + "\n" + _bloque("Precautions for Listening and Speaking", ""))
    assert limpiar_guion(t) == "Intro sin título.\n\nSegunda.\n\nTercera."


def test_limpiar_quita_la_cabecera_antigua_del_generador():
    t = "=" * 49 + "\nTEMA: Módulo 3: Colors - Primary\n" + "=" * 49 + "\n\nHola a todos.\n"
    assert limpiar_guion(t) == "Hola a todos."


def test_limpiar_junta_las_lineas_de_un_mismo_parrafo():
    assert limpiar_guion("Una línea\ncontinúa aquí.\n\n\n\nOtro párrafo.") == "Una línea continúa aquí.\n\nOtro párrafo."


# ---------------------------------------------------------------- nombres
def test_leer_nombre_extrae_nivel_modulo_posicion_y_tipo():
    f = leer_nombre("A1-M06-2 IA - Verb To Be (Affirmative) - He  She  It is.txt")
    assert (f.nivel, f.modulo, f.posicion, f.humano, f.id_clase) == ("A1", 6, 2, False, "A1-M06-2")
    assert f.titulo == "Verb To Be (Affirmative) - He  She  It is"
    h = leer_nombre("B2-M40-1 HUMANO - Money & Finance - Wealth & Poverty (REVISAR 640 pal).txt")
    assert h.humano and h.nivel == "B2" and h.revisar


def test_leer_nombre_ignora_lo_que_no_es_un_guion():
    for n in ("notas.txt", "A1-M06-2 IA - x.docx", "C1-M01-1 IA - a - b.txt", "A1-M1-2 IA - a - b.txt"):
        assert leer_nombre(n) is None


# ---------------------------------------------------------------- importación
@pytest.fixture
def drive(tmp_path):
    d = tmp_path / "Guiones"
    (d / "A1").mkdir(parents=True)
    (d / "B2").mkdir()
    (d / "A1" / "A1-M01-1 HUMANO - Alphabet - Letters.txt").write_text(_guion(), encoding="utf-8")
    (d / "A1" / "A1-M01-2 IA - Alphabet - Vowels.txt").write_text(_guion(hook="¿Sabías que…?"), encoding="utf-8")
    (d / "A1" / "A1-M01-3 IA - Alphabet - Names.txt").write_text(_guion(titulos=False), encoding="utf-8")
    (d / "B2" / "B2-M02-2 IA - Collocations - Verb + Noun.txt").write_text(_guion(), encoding="utf-8")
    (d / "A1" / "borrador.txt").write_text("no es una clase", encoding="utf-8")
    return d


def test_escanear_ordena_por_nivel_modulo_y_posicion(drive):
    ids = [f.id_clase for f in escanear(drive)]
    assert ids == ["A1-M01-1", "A1-M01-2", "A1-M01-3", "B2-M02-2"]


def test_importar_crea_solo_las_de_ia_con_idioma_segun_el_nivel(drive, tmp_path):
    raiz = tmp_path / "proyecto"
    r = importar_carpeta(raiz, drive)
    assert sorted(r["creadas"]) == ["A1-M01-2", "A1-M01-3", "B2-M02-2"]
    assert r["omitidas_humano"] == ["A1-M01-1"]
    a = json.loads((raiz / "clases" / "A1-M01-2.json").read_text(encoding="utf-8"))
    b = json.loads((raiz / "clases" / "B2-M02-2.json").read_text(encoding="utf-8"))
    assert (a["idioma"], a["voz"]) == (IDIOMA_POR_NIVEL["A1"], "colombiano") and b["idioma"] == "en"
    texto = (raiz / "clases" / "A1-M01-2.txt").read_text(encoding="utf-8")
    assert texto.startswith("¿Sabías que…?") and "The Definition" not in texto and RAYA not in texto


def test_importar_con_humanas_incluye_la_clase_humana(drive, tmp_path):
    r = importar_carpeta(tmp_path / "p", drive, solo_ia=False)
    assert "A1-M01-1" in r["creadas"] and r["omitidas_humano"] == []


def test_importar_dos_veces_no_duplica_ni_pisa_los_ajustes(drive, tmp_path):
    raiz = tmp_path / "proyecto"
    importar_carpeta(raiz, drive)
    logica.actualizar_clase(raiz, "A1-M01-2", idioma="es", escenarios="E3")        # el usuario ajusta una clase
    r = importar_carpeta(raiz, drive)
    assert r["creadas"] == [] and r["actualizadas"] == [] and len(r["sin_cambios"]) == 3
    meta = json.loads((raiz / "clases" / "A1-M01-2.json").read_text(encoding="utf-8"))
    assert meta["idioma"] == "es" and meta["escenarios"] == "E3"


def test_si_el_guion_cambia_en_drive_se_actualiza_el_texto_y_se_conservan_los_ajustes(drive, tmp_path):
    raiz = tmp_path / "proyecto"
    importar_carpeta(raiz, drive)
    logica.actualizar_clase(raiz, "A1-M01-2", escenarios="E3")
    (drive / "A1" / "A1-M01-2 IA - Alphabet - Vowels.txt").write_text(_guion(palabras=600, hook="Nuevo gancho."), encoding="utf-8")
    r = importar_carpeta(raiz, drive)
    assert r["actualizadas"] == ["A1-M01-2"]
    assert (raiz / "clases" / "A1-M01-2.txt").read_text(encoding="utf-8").startswith("Nuevo gancho.")
    assert json.loads((raiz / "clases" / "A1-M01-2.json").read_text(encoding="utf-8"))["escenarios"] == "E3"


def test_un_guion_demasiado_corto_se_ignora_con_el_motivo(drive, tmp_path):
    (drive / "A1" / "A1-M01-3 IA - Alphabet - Names.txt").write_text(_guion(palabras=120), encoding="utf-8")
    r = importar_carpeta(tmp_path / "p", drive)
    assert "A1-M01-3" not in r["creadas"]
    assert any(i["id"] == "A1-M01-3" and "corto" in i["motivo"] for i in r["ignoradas"])


def test_filtrar_por_nivel(drive, tmp_path):
    r = importar_carpeta(tmp_path / "p", drive, niveles=["B2"])
    assert r["creadas"] == ["B2-M02-2"]


def test_carpeta_inexistente_da_un_error_con_la_accion_a_seguir(tmp_path):
    with pytest.raises(ErrorAccionable) as e:
        importar_carpeta(tmp_path / "p", tmp_path / "no_existe")
    assert "carpeta" in str(e.value).lower()


def test_exportar_limpios_escribe_copias_sin_tocar_los_originales_y_es_repetible(drive, tmp_path):
    from src.guiones_drive import exportar_limpios
    original = (drive / "A1" / "A1-M01-2 IA - Alphabet - Vowels.txt").read_text(encoding="utf-8")
    destino = tmp_path / "A1 Limpio"
    r = exportar_limpios(drive / "A1", destino)
    assert len(r["escritos"]) == 3 and r["sin_cambios"] == []                       # incluye la humana: limpiar es para todas
    limpio = (destino / "A1-M01-2 IA - Alphabet - Vowels.txt").read_text(encoding="utf-8")
    assert RAYA not in limpio and "The Definition" not in limpio and limpio.startswith("¿Sabías que…?")
    assert (drive / "A1" / "A1-M01-2 IA - Alphabet - Vowels.txt").read_text(encoding="utf-8") == original
    assert exportar_limpios(drive / "A1", destino) == {"escritos": [], "sin_cambios": ["A1-M01-1", "A1-M01-2", "A1-M01-3"]}


def test_si_un_guion_esta_en_la_carpeta_y_en_la_limpia_se_importa_una_sola_vez(drive, tmp_path):
    from src.guiones_drive import exportar_limpios
    exportar_limpios(drive / "A1", drive / "A1 Limpio")
    fichas = [f for f in escanear(drive) if f.nivel == "A1"]
    assert [f.id_clase for f in fichas] == ["A1-M01-1", "A1-M01-2", "A1-M01-3"]
    assert all("Limpio" in str(f.ruta.parent) for f in fichas)
    assert len(importar_carpeta(tmp_path / "p", drive)["creadas"]) == 3


def test_si_drive_deja_una_copia_vacia_del_mismo_guion_se_usa_la_que_tiene_texto(drive, tmp_path):
    bueno = drive / "A1" / "A1-M01-2 IA - Alphabet - Vowels.txt"
    vacio = drive / "A1" / "A1-M01-2 IA - Alphabet - Vowels (1).txt"               # ordena antes que la buena por el espacio
    vacio.write_text("", encoding="utf-8")
    elegido = [f for f in escanear(drive) if f.id_clase == "A1-M01-2"]
    assert len(elegido) == 1 and elegido[0].ruta == bueno
    assert "A1-M01-2" in importar_carpeta(tmp_path / "p", drive)["creadas"]
