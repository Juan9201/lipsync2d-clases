"""Candado entre procesos: la webapp de voz numera sus archivos listando la carpeta y no es
segura ante peticiones simultáneas de varios trabajadores."""
import threading
import time

import pytest

from src.errores import TTSNoDisponible
from src.tts.candado import CandadoArchivo


def test_exclusion_mutua_entre_hilos(tmp_path):
    ruta = tmp_path / "tts.lock"
    contador = {"dentro": 0, "maximo": 0}

    def tarea():
        with CandadoArchivo(ruta):
            contador["dentro"] += 1
            contador["maximo"] = max(contador["maximo"], contador["dentro"])
            time.sleep(0.02)
            contador["dentro"] -= 1

    hilos = [threading.Thread(target=tarea) for _ in range(8)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert contador["maximo"] == 1 and not ruta.exists()


def test_un_candado_obsoleto_de_un_proceso_muerto_se_rompe(tmp_path):
    ruta = tmp_path / "tts.lock"
    ruta.mkdir()
    antiguo = time.time() - 5000
    import os
    os.utime(ruta, (antiguo, antiguo))
    with CandadoArchivo(ruta, obsoleto_s=60):
        assert ruta.exists()


def test_si_no_se_obtiene_a_tiempo_explica_que_hacer(tmp_path):
    ruta = tmp_path / "tts.lock"
    with CandadoArchivo(ruta):
        with pytest.raises(TTSNoDisponible) as exc:
            with CandadoArchivo(ruta, timeout_s=0.3, espera_s=0.05):
                pass
    assert "Qué hacer" in str(exc.value)
