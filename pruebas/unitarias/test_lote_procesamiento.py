"""FR-103, FR-104, FR-105, FR-106, FR-107: fallo aislado, reanudación, estado y protección de disco."""
from pathlib import Path

from src.errores import ErrorAccionable
from src.lote.cola import Cola, Trabajo
from src.lote.estado import resumen_texto
from src.lote.trabajadores import parametros_de, preparar_reanudacion, procesar_cola
from src.timeline import semilla_de_clase

GB = 1024 ** 3


def _cola(proyecto, n, lote="L"):
    cola = Cola(proyecto / "lote" / "cola.db")
    cola.encolar([Trabajo(id=f"clase_{i:04d}", lote=lote) for i in range(1, n + 1)])
    return cola


def _ejecutor_ok(t, raiz):
    salida = Path(raiz) / "salidas" / f"{t.id}_20261014.mp4"
    salida.write_bytes(b"mp4")
    return salida


def test_un_trabajo_defectuoso_no_detiene_a_los_demas(proyecto_tmp):
    cola = _cola(proyecto_tmp, 20)

    def ejecutor(t, raiz):
        if t.id == "clase_0007":
            raise ErrorAccionable("El audio está dañado", "Genera el audio de nuevo")
        return _ejecutor_ok(t, raiz)

    procesar_cola(cola, proyecto_tmp, ejecutor, espacio_libre=lambda p: 500 * GB, dormir=lambda s: None)
    r = cola.resumen()
    assert (r["hecho"], r["error"]) == (19, 1) and r["pendiente"] == 0
    err = next(t for t in cola.trabajos() if t.estado == "error")
    assert err.id == "clase_0007" and "audio está dañado" in err.error and "Qué hacer" in err.error


def test_un_error_inesperado_tambien_se_aisla_y_se_registra(proyecto_tmp):
    cola = _cola(proyecto_tmp, 3)

    def ejecutor(t, raiz):
        if t.id == "clase_0002":
            raise RuntimeError("boom")
        return _ejecutor_ok(t, raiz)

    procesar_cola(cola, proyecto_tmp, ejecutor, espacio_libre=lambda p: 500 * GB, dormir=lambda s: None)
    err = next(t for t in cola.trabajos() if t.estado == "error")
    assert "RuntimeError" in err.error and cola.resumen()["hecho"] == 2


def test_un_trabajo_con_su_mp4_ya_hecho_no_se_repite(proyecto_tmp):
    cola = _cola(proyecto_tmp, 2)
    (proyecto_tmp / "salidas" / "clase_0001_20261013.mp4").write_bytes(b"mp4 de ayer")
    llamadas = []

    def ejecutor(t, raiz):
        llamadas.append(t.id)
        return _ejecutor_ok(t, raiz)

    procesar_cola(cola, proyecto_tmp, ejecutor, espacio_libre=lambda p: 500 * GB, dormir=lambda s: None)
    assert llamadas == ["clase_0002"] and cola.resumen()["hecho"] == 2


def test_con_poco_disco_la_cola_espera_y_retoma_al_liberar_espacio(proyecto_tmp, capsys):
    cola = _cola(proyecto_tmp, 2)
    lecturas = iter([2 * GB, 3 * GB, 400 * GB] + [400 * GB] * 20)
    esperas = []
    procesar_cola(cola, proyecto_tmp, _ejecutor_ok, espacio_libre=lambda p: next(lecturas),
                  espacio_minimo_gb=20, dormir=esperas.append)
    assert esperas[:2] == [30, 30] and cola.resumen()["hecho"] == 2
    err = capsys.readouterr().err
    assert "espacio" in err.lower() and "20 GB" in err


def test_tras_un_corte_se_recupera_y_se_limpian_los_parciales(proyecto_tmp):
    cola = _cola(proyecto_tmp, 3)
    huerfano = cola.reclamar()
    cola._forzar_latido(huerfano.id, 1.0)                                  # el proceso murió hace mucho
    (proyecto_tmp / "salidas" / f"{huerfano.id}_20261014.part.mp4").write_bytes(b"mitad")
    hecho = cola.reclamar()
    cola.terminar(hecho.id, "ok")
    recuperados = preparar_reanudacion(cola, proyecto_tmp, max_edad_s=60)
    assert recuperados == [huerfano.id]
    assert not list((proyecto_tmp / "salidas").glob("*.part.mp4"))
    procesar_cola(cola, proyecto_tmp, _ejecutor_ok, espacio_libre=lambda p: 500 * GB, dormir=lambda s: None)
    assert cola.resumen()["hecho"] == 3


def test_la_semilla_de_cada_clase_se_deriva_de_su_id(proyecto_tmp):
    a = parametros_de(Trabajo(id="clase_0001", personaje="profesor", audio="a.mp3"), proyecto_tmp)
    b = parametros_de(Trabajo(id="clase_0001", personaje="profesor", audio="a.mp3"), proyecto_tmp)
    c = parametros_de(Trabajo(id="clase_0002", personaje="profesor", audio="a.mp3"), proyecto_tmp)
    assert (a.clase_id, a.semilla) == (b.clase_id, b.semilla) and a.clase_id == "clase_0001"
    assert semilla_de_clase(a.clase_id, a.semilla) != semilla_de_clase(c.clase_id, c.semilla)


def test_la_semilla_manual_del_manifiesto_manda(proyecto_tmp):
    p = parametros_de(Trabajo(id="x", personaje="profesor", audio="a.mp3", semilla=42), proyecto_tmp)
    assert p.semilla == 42


def test_el_estado_muestra_progreso_tiempos_y_errores(proyecto_tmp):
    cola = _cola(proyecto_tmp, 4)
    t = cola.reclamar(); cola.terminar(t.id, "x")
    t = cola.reclamar(); cola.fallar(t.id, "Audio dañado. Qué hacer: genera otro")
    cola.reclamar()
    texto = resumen_texto(cola, "L")
    assert "4 clases" in texto and "1 hechas" in texto and "1 en proceso" in texto
    assert "1 pendientes" in texto and "1 con error" in texto
    assert "clase_0002" in texto and "Audio dañado" in texto
    assert "por clase" in texto and "Estimación" in texto
