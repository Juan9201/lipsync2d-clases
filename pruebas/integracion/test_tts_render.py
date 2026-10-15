"""FR-010, FR-013: sin --audio el render genera la voz con el proveedor elegido; si falla,
se detiene con la causa y las alternativas."""
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from src.biblioteca.placeholders import crear_pose_placeholder
from src.cli import main
from src.errores import TTSNoDisponible
from src.tts.base import EstadoProveedor, OpcionesTTS

RAIZ = Path(__file__).resolve().parents[2]
FFMPEG = RAIZ / "herramientas" / "ffmpeg" / "bin" / "ffmpeg.exe"
RHUBARB = RAIZ / "herramientas" / "rhubarb" / "rhubarb.exe"
EJEMPLO = RAIZ / "Temp Real Assest Testing" / "tts_008.mp3"

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not (FFMPEG.exists() and RHUBARB.exists() and EJEMPLO.exists()),
                                 reason="faltan ffmpeg, Rhubarb o el audio de ejemplo")]


class ProveedorCaido:
    nombre, extension, limite_caracteres, max_reintentos = "gemini-studio", "mp3", 8000, 1

    def comprobar(self):
        return EstadoProveedor(False, "caído")

    def sintetizar(self, texto, destino, opciones):
        raise TTSNoDisponible("No se pudo conectar con gemini-tts-studio",
                              "Inicia la webapp, o usa --tts piper, o entrega --audio")


class ProveedorQueGenera:
    nombre, extension, limite_caracteres, max_reintentos = "gemini-studio", "mp3", 8000, 1
    textos = []

    def comprobar(self):
        return EstadoProveedor(True, "ok")

    def sintetizar(self, texto, destino, opciones):
        self.textos.append(texto)
        subprocess.run([str(FFMPEG), "-v", "error", "-y", "-t", "4", "-i", str(EJEMPLO), "-c", "copy",
                        "-f", "mp3", str(destino)], check=True)
        return destino


@pytest.fixture
def proyecto(proyecto_tmp):
    crear_pose_placeholder(proyecto_tmp / "personajes" / "profesor" / "poses" / "P1_demo", "P1", lienzo=(1280, 720))
    fondo = proyecto_tmp / "escenarios" / "E1_aula" / "fondo.png"
    fondo.parent.mkdir(parents=True)
    Image.new("RGB", (1280, 720), (90, 140, 200)).save(fondo)
    guion = proyecto_tmp / "clases" / "clase_0001.txt"
    guion.write_text("Hola a todos. [pose:P1] Hoy hablamos de frases fijas. [short pause] Gracias.",
                     encoding="utf-8")
    return proyecto_tmp, guion


def test_tts_caido_se_detiene_con_causa_y_alternativas(proyecto, monkeypatch, capsys):
    raiz, guion = proyecto
    monkeypatch.setattr("src.tts.obtener_proveedor", lambda nombre, raiz=None, genero=None: (ProveedorCaido(), OpcionesTTS()))
    codigo = main(["--personaje", "profesor", "--guion", str(guion)], raiz=raiz)
    err = capsys.readouterr().err
    assert codigo == 1 and "gemini-tts-studio" in err and "piper" in err and "--audio" in err
    assert not list((raiz / "salidas").glob("*.mp4"))


def test_sin_audio_genera_la_voz_y_renderiza(proyecto, monkeypatch, capsys):
    raiz, guion = proyecto
    prov = ProveedorQueGenera()
    prov.textos = []
    monkeypatch.setattr("src.tts.obtener_proveedor", lambda nombre, raiz=None, genero=None: (prov, OpcionesTTS()))
    codigo = main(["--personaje", "profesor", "--guion", str(guion)], raiz=raiz)
    assert codigo == 0, capsys.readouterr().err
    assert (raiz / "clases" / "clase_0001.mp3").is_file()
    assert len(list((raiz / "salidas").glob("clase_0001_*.mp4"))) == 1
    assert prov.textos and "[pose:" not in prov.textos[0] and "[short pause]" in prov.textos[0]   # FR-012


def test_guion_inexistente(proyecto, capsys):
    raiz, _ = proyecto
    codigo = main(["--personaje", "profesor", "--guion", str(raiz / "clases" / "no.txt")], raiz=raiz)
    assert codigo == 1 and "Qué hacer" in capsys.readouterr().err
