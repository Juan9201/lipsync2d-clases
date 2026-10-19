"""El casting de la voz (2026-10-19): una sola voz masculina (podcaster-3) con perfil colombiano (por defecto) o neutro, en cualquier idioma;
la interfaz ya no permite cambiar de voz."""
import csv
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

from src.errores import ErrorAccionable, TTSNoDisponible
from src.lote.cola import Cola, Trabajo
from src.lote.manifiesto import leer_manifiesto
from src.tts import obtener_proveedor
from src.ui import logica
from src.ui.servidor import crear_servidor

RAIZ = Path(__file__).resolve().parents[2]


def test_tts_yaml_del_proyecto_tiene_el_casting_decidido():
    _, op = obtener_proveedor("gemini-studio", RAIZ)
    assert op.voz == "es-419-podcaster-3" and op.idioma == "es-419" and "colombiano" in op.estilo
    _, neutro = obtener_proveedor("gemini-studio", RAIZ, perfil="neutro")
    assert neutro.voz == "es-419-podcaster-3" and neutro.estilo == ""


@pytest.mark.parametrize("idioma", ["es", "en", "mixto", None])
def test_la_misma_voz_sirve_para_todos_los_idiomas(idioma):
    _, op = obtener_proveedor("gemini-studio", RAIZ, idioma=idioma)
    assert op.voz == "es-419-podcaster-3" and op.idioma == "es-419"


def test_un_perfil_desconocido_da_un_error_claro(proyecto_tmp):
    (proyecto_tmp / "tts.yaml").write_text(yaml.safe_dump({"gemini-studio": {"perfiles": {"a": {"estilo": "x"}}}}), encoding="utf-8")
    with pytest.raises(TTSNoDisponible) as exc:
        obtener_proveedor("gemini-studio", proyecto_tmp, perfil="b")
    assert "b" in str(exc.value) and "a" in str(exc.value)


def _manifiesto(proyecto_tmp, voz):
    (proyecto_tmp / "g.txt").write_text("hola", encoding="utf-8")
    ruta = proyecto_tmp / "m.csv"
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "guion", "voz"])
        w.writeheader()
        w.writerow({"id": "c1", "guion": str(proyecto_tmp / "g.txt"), "voz": voz})
    return ruta


def test_el_manifiesto_y_la_cola_llevan_el_perfil_de_voz(proyecto_tmp):
    assert leer_manifiesto(_manifiesto(proyecto_tmp, "neutro"), proyecto_tmp)[0].voz == "neutro"
    assert leer_manifiesto(_manifiesto(proyecto_tmp, ""), proyecto_tmp)[0].voz == "colombiano"
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    cola.encolar([Trabajo(id="x", voz="neutro")])
    assert cola.reclamar().voz == "neutro"


def test_una_voz_invalida_en_el_manifiesto_se_rechaza(proyecto_tmp):
    with pytest.raises(ErrorAccionable) as exc:
        leer_manifiesto(_manifiesto(proyecto_tmp, "robot"), proyecto_tmp)
    assert "robot" in str(exc.value) and "colombiano" in str(exc.value)


def test_el_trabajador_genera_la_voz_con_el_perfil_de_la_clase(proyecto_tmp, monkeypatch):
    from src.lote import trabajadores
    llamadas = []

    def falsa(guion, tts, raiz, genero=None, idioma=None, perfil=None):
        llamadas.append((idioma, perfil))
        return proyecto_tmp / "a.mp3"
    monkeypatch.setattr("src.cli.generar_voz", falsa)
    monkeypatch.setattr(trabajadores, "renderizar", lambda params, raiz: Path("salida.mp4"))
    trabajadores.ejecutar_trabajo(Trabajo(id="c1", guion=str(proyecto_tmp / "g.txt"), idioma="en", voz="neutro"), proyecto_tmp)
    assert llamadas == [("en", "neutro")]


def test_la_clase_de_la_interfaz_tiene_voz_colombiana_por_defecto_y_solo_admite_las_dos(proyecto_tmp):
    assert logica.guardar_clase(proyecto_tmp, "hola", "c1")["voz"] == "colombiano"
    assert logica.actualizar_clase(proyecto_tmp, "c1", voz="neutro")["voz"] == "neutro"
    with pytest.raises(ErrorAccionable):
        logica.actualizar_clase(proyecto_tmp, "c1", voz="aleatoria")


def test_la_interfaz_ya_no_ofrece_cambiar_las_voces(proyecto_tmp):
    for nombre in ("voces_guardadas", "guardar_voces", "listar_voces_remoto", "muestra_de_voz"):
        assert not hasattr(logica, nombre)
    html = (RAIZ / "src" / "ui" / "web" / "index.html").read_text(encoding="utf-8")
    js = (RAIZ / "src" / "ui" / "web" / "app.js").read_text(encoding="utf-8")
    assert "btn-voces" not in html and "/api/voces" not in js and "/api/muestra" not in js
    servidor = crear_servidor(proyecto_tmp, 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}"
        for ruta, cuerpo in (("/api/voces", None), ("/api/muestra", {}), ("/api/voces", {"idioma": "es", "hombre": "x"})):
            req = urllib.request.Request(url + ruta, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                         headers={"X-Lipsync": "1", "Content-Type": "application/json"})
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            assert exc.value.code == 404
    finally:
        servidor.shutdown()
        servidor.server_close()
