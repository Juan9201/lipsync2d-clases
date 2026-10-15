"""FR-101, FR-066, FR-107: manifiesto de lote (CSV) y creación desde una carpeta de clases."""
import csv

import pytest

from src.errores import ErrorAccionable
from src.lote.cola import Cola
from src.lote.manifiesto import crear_manifiesto, encolar_manifiesto, leer_manifiesto


def _clases(proyecto, n=20, sin_audio=(), sin_guion=()):
    carpeta = proyecto / "clases"
    for i in range(1, n + 1):
        nombre = f"clase_{i:04d}"
        if nombre not in sin_guion:
            (carpeta / f"{nombre}.txt").write_text(f"Guion {i}.", encoding="utf-8")
        if nombre not in sin_audio:
            (carpeta / f"{nombre}.mp3").write_bytes(b"x")
    return carpeta


def test_crea_un_manifiesto_de_20_filas_desde_la_carpeta(proyecto_tmp):
    carpeta = _clases(proyecto_tmp)
    destino = proyecto_tmp / "lote" / "manifiestos" / "2026-10-A.csv"
    inf = crear_manifiesto(carpeta, "profesor", "2026-10-A", destino)
    filas = list(csv.DictReader(destino.open(encoding="utf-8-sig")))
    assert inf.filas == 20 and len(filas) == 20
    assert filas[0]["id"] == "clase_0001" and filas[0]["personaje"] == "profesor"
    assert filas[0]["audio"].endswith("clase_0001.mp3") and filas[0]["guion"].endswith("clase_0001.txt")
    assert not inf.sin_audio and not inf.sin_guion


def test_reporta_guiones_sin_audio_y_audios_sin_guion(proyecto_tmp):
    carpeta = _clases(proyecto_tmp, 5, sin_audio=("clase_0002",), sin_guion=("clase_0004",))
    inf = crear_manifiesto(carpeta, "profesor", "L", proyecto_tmp / "lote" / "manifiestos" / "L.csv")
    assert inf.sin_audio == ["clase_0002"] and inf.sin_guion == ["clase_0004"]
    assert inf.filas == 5


def test_leer_valido_aplica_los_valores_por_defecto(proyecto_tmp):
    carpeta = _clases(proyecto_tmp, 2)
    destino = proyecto_tmp / "lote" / "manifiestos" / "L.csv"
    crear_manifiesto(carpeta, "profesor", "L", destino)
    trabajos = leer_manifiesto(destino, proyecto_tmp)
    assert [t.id for t in trabajos] == ["clase_0001", "clase_0002"]
    assert all(t.lote == "L" and t.resolucion == "1280x720" and t.tts == "gemini-studio" for t in trabajos)


def test_errores_por_fila_se_informan_todos_juntos(proyecto_tmp):
    ruta = proyecto_tmp / "lote" / "manifiestos" / "malo.csv"
    ruta.write_text(
        "id,guion,audio,personaje,escenarios,poses,resolucion,semilla,tts,lote\n"
        "a,,no_existe.mp3,profesor,,,1280x720,,,L\n"          # audio inexistente
        "b,,,profesor,,,1280x720,,,L\n"                       # sin guion ni audio
        "c,,x.mp3,profesor,,,800x600,,,L\n"                   # resolución inválida
        "a,,x.mp3,profesor,,,1280x720,,,L\n"                  # id duplicado
        "mala id,,x.mp3,profesor,,,1280x720,,,L\n", encoding="utf-8")
    (proyecto_tmp / "x.mp3").write_bytes(b"x")
    with pytest.raises(ErrorAccionable) as exc:
        leer_manifiesto(ruta, proyecto_tmp)
    msg = str(exc.value)
    for esperado in ("fila 2", "no existe", "fila 3", "ni guion ni audio", "fila 4", "800x600", "fila 5", "duplicado", "fila 6"):
        assert esperado in msg, esperado
    assert "Qué hacer" in msg


def test_encolar_crea_trabajos_con_la_etiqueta_del_lote(proyecto_tmp):
    carpeta = _clases(proyecto_tmp, 20)
    destino = proyecto_tmp / "lote" / "manifiestos" / "L.csv"
    crear_manifiesto(carpeta, "profesor", "2026-10-A", destino)
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    nuevos, duplicados = encolar_manifiesto(cola, destino, proyecto_tmp)
    assert nuevos == 20 and duplicados == []
    assert {t.lote for t in cola.trabajos()} == {"2026-10-A"}
    assert encolar_manifiesto(cola, destino, proyecto_tmp) == (0, [f"clase_{i:04d}" for i in range(1, 21)])
