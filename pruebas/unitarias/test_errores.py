"""NFR-006: todo error visible está en español e indica qué hacer."""
import pytest

from src.errores import ErrorAccionable, EntornoIncompleto, TTSNoDisponible


def test_mensaje_incluye_causa_y_sugerencia():
    e = ErrorAccionable("No se encontró ffmpeg", "Ejecuta instalar.ps1")
    texto = str(e)
    assert "No se encontró ffmpeg" in texto
    assert "Qué hacer: Ejecuta instalar.ps1" in texto
    assert e.causa == "No se encontró ffmpeg"
    assert e.sugerencia == "Ejecuta instalar.ps1"


@pytest.mark.parametrize("causa,sugerencia", [("", "algo"), ("algo", ""), ("  ", "x")])
def test_causa_y_sugerencia_son_obligatorias(causa, sugerencia):
    with pytest.raises(ValueError):
        ErrorAccionable(causa, sugerencia)


def test_subclases_son_error_accionable():
    assert issubclass(EntornoIncompleto, ErrorAccionable)
    assert issubclass(TTSNoDisponible, ErrorAccionable)
    assert isinstance(TTSNoDisponible("sin red", "usa piper"), Exception)
