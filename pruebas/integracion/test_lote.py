"""FR-101 a FR-107: un lote real con varios trabajadores, fallo aislado, reanudación y reproducibilidad."""
import subprocess
import time

import pytest

from pruebas.utiles import EJEMPLO, FFMPEG, recortar_audio
from src.lote.cola import Cola
from src.lote.manifiesto import crear_manifiesto, encolar_manifiesto
from src.lote.trabajadores import correr, preparar_reanudacion

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and EJEMPLO.exists()), reason="faltan ffmpeg o el audio de ejemplo")]


def _clases(proyecto, n=4, seg=6, defectuosa=None):
    for i in range(1, n + 1):
        nombre = f"clase_{i:04d}"
        recortar_audio(EJEMPLO, proyecto / "clases" / f"{nombre}.mp3", seg, inicio=10 + 7 * i)
        (proyecto / "clases" / f"{nombre}.txt").write_text(f"Texto de la clase {i}.", encoding="utf-8")
    if defectuosa:
        (proyecto / "clases" / f"{defectuosa}.mp3").write_bytes(b"esto no es un mp3")
        (proyecto / "clases" / f"{defectuosa}.txt").write_text("Clase con audio dañado.", encoding="utf-8")


def _encolar(proyecto, lote="L"):
    csv_ruta = proyecto / "lote" / "manifiestos" / f"{lote}.csv"
    crear_manifiesto(proyecto / "clases", "profe", lote, csv_ruta)
    cola = Cola(proyecto / "lote" / "cola.db")
    encolar_manifiesto(cola, csv_ruta, proyecto)
    return cola


def _huella(video):
    out = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(video), "-an", "-f", "framemd5", "-"],
                         capture_output=True, text=True, check=True).stdout
    return [l.split(",")[-1].strip() for l in out.splitlines() if l and not l.startswith("#")]


def test_lote_con_dos_trabajadores_y_una_clase_defectuosa(proyecto_con_assets, capsys):
    p = proyecto_con_assets
    _clases(p, 4, defectuosa="clase_0005")
    cola = _encolar(p)
    t0 = time.perf_counter()
    codigo = correr(p, p / "lote" / "cola.db", trabajadores=2, espacio_minimo_gb=0.001, intervalo_s=0.5)
    r = cola.resumen()
    print(f"\nlote de 5 (4 buenas + 1 dañada) con 2 trabajadores: {time.perf_counter() - t0:.1f} s")
    assert codigo == 1 and (r["hecho"], r["error"], r["pendiente"], r["en_proceso"]) == (4, 1, 0, 0)
    assert len(list((p / "salidas").glob("clase_000[1-4]_*.mp4"))) == 4
    assert not list((p / "salidas").glob("*.part.mp4"))
    err = cola.trabajos("error")[0]
    assert err.id == "clase_0005" and "Qué hacer" in err.error
    salida = capsys.readouterr().out
    assert "4 hechas" in salida and "1 con error" in salida and "clase_0005" in salida


def test_tras_un_corte_el_lote_se_reanuda_sin_repetir_lo_terminado(proyecto_con_assets):
    p = proyecto_con_assets
    _clases(p, 3)
    cola = _encolar(p)
    # Simula un corte: la clase 1 terminó, la 2 quedó a medias y la 3 sin empezar
    hecha = cola.reclamar()
    from src.render import ParametrosRender, renderizar
    renderizar(ParametrosRender(personaje="profe", audio=p / "clases" / "clase_0001.mp3", clase_id="clase_0001"), p)
    cola.terminar(hecha.id, "salidas/clase_0001")
    a_medias = cola.reclamar()
    cola._forzar_latido(a_medias.id, 1.0)
    (p / "salidas" / "clase_0002_20261014.part.mp4").write_bytes(b"mitad")
    mtime_1 = next((p / "salidas").glob("clase_0001_*.mp4")).stat().st_mtime_ns
    assert preparar_reanudacion(cola, p) == ["clase_0002"]
    assert correr(p, p / "lote" / "cola.db", 2, 0.001, intervalo_s=0.5) == 0
    assert cola.resumen()["hecho"] == 3
    assert next((p / "salidas").glob("clase_0001_*.mp4")).stat().st_mtime_ns == mtime_1     # no se rehízo
    assert not list((p / "salidas").glob("*.part.mp4"))


def test_repetir_un_lote_reproduce_los_mismos_videos(proyecto_con_assets):
    p = proyecto_con_assets
    _clases(p, 2, seg=5)
    cola = _encolar(p)
    correr(p, p / "lote" / "cola.db", 2, 0.001, intervalo_s=0.5)
    primeros = {f.name.split("_20")[0]: _huella(f) for f in (p / "salidas").glob("*.mp4")}
    for f in (p / "salidas").glob("*.mp4"):
        f.unlink()
    for t in cola.trabajos():                                  # el mismo lote, otra vez
        with cola._conexion() as con:
            con.execute("UPDATE trabajos SET estado='pendiente' WHERE id=?", (t.id,))
    correr(p, p / "lote" / "cola.db", 2, 0.001, intervalo_s=0.5)
    segundos = {f.name.split("_20")[0]: _huella(f) for f in (p / "salidas").glob("*.mp4")}
    assert primeros.keys() == segundos.keys() == {"clase_0001", "clase_0002"}
    assert primeros == segundos and len(primeros["clase_0001"]) > 100
