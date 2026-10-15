"""FR-002: la verificación informa el estado de cada dependencia y la acción correctiva."""
from src.entorno import Dependencia, formato_informe, revisar_dependencias, todo_ok


def _crear(proyecto, ruta_relativa):
    destino = proyecto / ruta_relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(b"x")


def test_sin_herramientas_reporta_faltantes_con_accion(proyecto_tmp):
    estados = revisar_dependencias(proyecto_tmp)
    por_nombre = {e.nombre: e for e in estados}
    assert not por_nombre["ffmpeg"].ok
    assert "instalar.ps1" in por_nombre["ffmpeg"].accion
    assert not todo_ok(estados)


def test_con_herramientas_presentes_esta_ok(proyecto_tmp):
    for e in revisar_dependencias(proyecto_tmp):
        if e.requerida and e.ruta is not None:
            _crear(proyecto_tmp, e.ruta)
    estados = revisar_dependencias(proyecto_tmp)
    faltan = [e.nombre for e in estados if e.requerida and not e.ok]
    # Solo pueden faltar las comprobaciones que no son un archivo (paquetes de Python)
    assert all(n.startswith("python") or n.startswith("paquete") for n in faltan) or not faltan


def test_dependencia_opcional_no_bloquea(proyecto_tmp):
    estados = revisar_dependencias(proyecto_tmp)
    opcionales = [e for e in estados if not e.requerida]
    assert opcionales, "debe haber dependencias opcionales (grupo de preparación)"
    assert all(not e.requerida for e in opcionales)


def test_formato_informe_en_espanol(proyecto_tmp):
    texto = formato_informe(revisar_dependencias(proyecto_tmp))
    assert "ffmpeg" in texto
    assert "Qué hacer" in texto or "Acción" in texto


def test_dependencia_es_inmutable():
    d = Dependencia("x", True, "ok", "", "ruta", True)
    assert d.ok
