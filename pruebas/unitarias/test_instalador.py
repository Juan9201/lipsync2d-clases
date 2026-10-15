"""FR-001 / P4: descargas verificadas con SHA-256, sin red externa (servidor local)."""
import hashlib
import http.server
import threading
import zipfile
from functools import partial

import pytest

from src.errores import EntornoIncompleto
from src.instalador import descargar_verificado, extraer_zip, sha256_de


@pytest.fixture
def servidor(tmp_path):
    carpeta = tmp_path / "servido"
    carpeta.mkdir()
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(carpeta))
    handler.log_message = lambda *a, **k: None  # silencio
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield carpeta, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_descarga_correcta_verifica_checksum(servidor, proyecto_tmp):
    carpeta, url = servidor
    (carpeta / "a.bin").write_bytes(b"contenido de prueba")
    esperado = hashlib.sha256(b"contenido de prueba").hexdigest()
    destino = proyecto_tmp / "herramientas" / "a.bin"
    descargar_verificado(f"{url}/a.bin", destino, esperado)
    assert destino.read_bytes() == b"contenido de prueba"
    assert sha256_de(destino) == esperado


def test_checksum_incorrecto_borra_y_explica(servidor, proyecto_tmp):
    carpeta, url = servidor
    (carpeta / "a.bin").write_bytes(b"otro contenido")
    destino = proyecto_tmp / "herramientas" / "a.bin"
    with pytest.raises(EntornoIncompleto) as exc:
        descargar_verificado(f"{url}/a.bin", destino, "0" * 64)
    assert "checksum" in str(exc.value).lower()
    assert not destino.exists()


def test_descarga_idempotente_si_ya_existe_y_coincide(servidor, proyecto_tmp):
    carpeta, url = servidor
    (carpeta / "a.bin").write_bytes(b"abc")
    esperado = hashlib.sha256(b"abc").hexdigest()
    destino = proyecto_tmp / "herramientas" / "a.bin"
    descargar_verificado(f"{url}/a.bin", destino, esperado)
    (carpeta / "a.bin").unlink()  # si intentara descargar de nuevo, fallaría
    descargar_verificado(f"{url}/a.bin", destino, esperado)
    assert destino.exists()


def test_url_inaccesible_da_error_accionable(proyecto_tmp):
    with pytest.raises(EntornoIncompleto) as exc:
        descargar_verificado("http://127.0.0.1:9/nada.bin", proyecto_tmp / "x.bin", "0" * 64)
    assert "Qué hacer" in str(exc.value)


def test_extraer_zip_en_ruta_con_acentos(proyecto_tmp):
    zip_ruta = proyecto_tmp / "paquete ñ.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        z.writestr("dir/archivo.txt", "hola")
    destino = proyecto_tmp / "herramientas" / "destino áé"
    extraer_zip(zip_ruta, destino)
    assert (destino / "dir" / "archivo.txt").read_text() == "hola"


def test_extraer_zip_rechaza_rutas_peligrosas(proyecto_tmp):
    zip_ruta = proyecto_tmp / "malo.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        z.writestr("../fuera.txt", "x")
    with pytest.raises(EntornoIncompleto):
        extraer_zip(zip_ruta, proyecto_tmp / "destino")


def test_extraer_zip_quitando_la_carpeta_raiz(proyecto_tmp):
    zip_ruta = proyecto_tmp / "paquete.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        z.writestr("Raiz-1.0/bin/herramienta.exe", "x")
        z.writestr("Raiz-1.0/LEEME.txt", "y")
    destino = proyecto_tmp / "herramientas" / "herr"
    extraer_zip(zip_ruta, destino, quitar_raiz=True)
    assert (destino / "bin" / "herramienta.exe").is_file()
    assert (destino / "LEEME.txt").is_file()
    assert not (destino / "Raiz-1.0").exists()


def test_instalar_desde_manifiesto_descarga_y_extrae(servidor, proyecto_tmp):
    import json
    from src.instalador import instalar_desde_manifiesto
    carpeta, url = servidor
    zip_servido = carpeta / "h.zip"
    with zipfile.ZipFile(zip_servido, "w") as z:
        z.writestr("Raiz/h.exe", "x")
    manifiesto = [{
        "archivo": "h.zip", "url": f"{url}/h.zip", "sha256": sha256_de(zip_servido),
        "extraer_en": "herramientas/h", "quitar_raiz": True,
    }]
    (proyecto_tmp / "herramientas" / "manifiesto_descargas.json").write_text(
        json.dumps(manifiesto), encoding="utf-8")
    instalar_desde_manifiesto(proyecto_tmp)
    assert (proyecto_tmp / "herramientas" / "h" / "h.exe").is_file()
    # Segunda ejecución: idempotente
    instalar_desde_manifiesto(proyecto_tmp)


def test_manifiesto_copia_archivos_sueltos_al_destino(servidor, proyecto_tmp):
    import json
    from src.instalador import instalar_desde_manifiesto
    carpeta, url = servidor
    (carpeta / "voz.onnx").write_bytes(b"modelo de voz")
    manifiesto = [{"archivo": "voz.onnx", "url": f"{url}/voz.onnx",
                   "sha256": hashlib.sha256(b"modelo de voz").hexdigest(),
                   "copiar_a": "modelos/piper/voz ñ.onnx"}]
    (proyecto_tmp / "herramientas" / "manifiesto_descargas.json").write_text(
        json.dumps(manifiesto), encoding="utf-8")
    instalar_desde_manifiesto(proyecto_tmp)
    assert (proyecto_tmp / "modelos" / "piper" / "voz ñ.onnx").read_bytes() == b"modelo de voz"


def test_los_items_del_grupo_preparacion_solo_se_instalan_si_se_piden(servidor, proyecto_tmp):
    import json
    from src.instalador import instalar_desde_manifiesto
    carpeta, url = servidor
    (carpeta / "base.bin").write_bytes(b"base")
    (carpeta / "pesado.bin").write_bytes(b"pesado")
    manifiesto = [
        {"archivo": "base.bin", "url": f"{url}/base.bin", "sha256": hashlib.sha256(b"base").hexdigest(),
         "copiar_a": "herramientas/base.bin"},
        {"archivo": "pesado.bin", "grupo": "preparacion", "url": f"{url}/pesado.bin",
         "sha256": hashlib.sha256(b"pesado").hexdigest(), "copiar_a": "modelos/prep/pesado.bin"}]
    (proyecto_tmp / "herramientas" / "manifiesto_descargas.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    instalar_desde_manifiesto(proyecto_tmp)
    assert (proyecto_tmp / "herramientas" / "base.bin").exists()
    assert not (proyecto_tmp / "modelos" / "prep" / "pesado.bin").exists()
    instalar_desde_manifiesto(proyecto_tmp, preparacion=True)
    assert (proyecto_tmp / "modelos" / "prep" / "pesado.bin").exists()
