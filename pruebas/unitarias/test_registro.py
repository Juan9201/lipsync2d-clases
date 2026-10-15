"""P9: logs claros por etapa con tiempos."""
import logging
import time

import pytest

from src.registro import etapa, obtener_logger


def test_etapa_registra_inicio_fin_y_duracion(caplog):
    log = obtener_logger("prueba.etapa")
    with caplog.at_level(logging.INFO, logger="prueba.etapa"):
        with etapa(log, "render") as info:
            time.sleep(0.02)
    assert info["duracion_s"] >= 0.02
    mensajes = [r.getMessage() for r in caplog.records]
    assert any("[render] inicio" in m for m in mensajes)
    assert any("[render] fin" in m and "s" in m for m in mensajes)


def test_etapa_registra_error_y_relanza(caplog):
    log = obtener_logger("prueba.error")
    with caplog.at_level(logging.INFO, logger="prueba.error"):
        with pytest.raises(RuntimeError):
            with etapa(log, "tts"):
                raise RuntimeError("falló")
    assert any("[tts] error" in r.getMessage() for r in caplog.records)


def test_logger_escribe_archivo_por_trabajo(proyecto_tmp):
    archivo = proyecto_tmp / "logs" / "clase_0001.log"
    log = obtener_logger("prueba.archivo", archivo=archivo)
    log.info("hola áéí")
    for h in log.handlers:
        h.flush()
    assert "hola áéí" in archivo.read_text(encoding="utf-8")


def test_cambiar_de_archivo_no_sigue_escribiendo_en_el_anterior(proyecto_tmp):
    """En un trabajador que procesa miles de clases, cada log solo recibe los mensajes de su clase."""
    primero = proyecto_tmp / "logs" / "a.log"
    segundo = proyecto_tmp / "logs" / "b.log"
    log = obtener_logger("prueba.rotacion", archivo=primero)
    log.info("mensaje de A")
    log = obtener_logger("prueba.rotacion", archivo=segundo)
    log.info("mensaje de B")
    for h in log.handlers:
        h.flush()
    assert "mensaje de A" in primero.read_text(encoding="utf-8") and "mensaje de B" not in primero.read_text(encoding="utf-8")
    assert "mensaje de B" in segundo.read_text(encoding="utf-8")
    assert len([h for h in log.handlers if hasattr(h, "baseFilename")]) == 1
