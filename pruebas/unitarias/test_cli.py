"""FR-070, NFR-006: argumentos de la CLI y mensajes de error en español."""
import pytest

from src.cli import construir_parser, main


def test_acepta_los_argumentos_del_contrato():
    args = construir_parser().parse_args([
        "--guion", "g.txt", "--personaje", "profesor", "--audio", "a.mp3",
        "--tts", "edge", "--resolucion", "1920x1080", "--seed", "7"])
    assert args.tts == "edge" and args.resolucion == "1920x1080" and args.seed == 7


def test_valores_por_defecto():
    args = construir_parser().parse_args(["--personaje", "profesor", "--audio", "a.mp3"])
    assert args.tts == "gemini-studio" and args.resolucion == "1280x720" and args.seed == 0


@pytest.mark.parametrize("extra", [["--resolucion", "800x600"], ["--tts", "piper"], ["--seed", "x"]])
def test_rechaza_valores_invalidos(extra, capsys):
    with pytest.raises(SystemExit) as e:
        construir_parser().parse_args(["--personaje", "p", "--audio", "a.mp3", *extra])
    assert e.value.code == 2


def test_audio_inexistente_da_error_en_espanol(proyecto_tmp, capsys):
    codigo = main(["--personaje", "profesor", "--audio", str(proyecto_tmp / "no_existe.mp3")],
                  raiz=proyecto_tmp)
    err = capsys.readouterr().err
    assert codigo == 1 and "ERROR" in err and "no existe" in err and "Qué hacer" in err


def test_sin_audio_ni_guion_pide_uno(proyecto_tmp, capsys):
    codigo = main(["--personaje", "profesor"], raiz=proyecto_tmp)
    assert codigo == 1 and "Qué hacer" in capsys.readouterr().err


def test_personaje_sin_poses_explica_que_hacer(proyecto_tmp, capsys):
    audio = proyecto_tmp / "clases" / "a.mp3"
    audio.write_bytes(b"x")
    codigo = main(["--personaje", "profesor", "--audio", str(audio)], raiz=proyecto_tmp)
    assert codigo == 1 and "Qué hacer" in capsys.readouterr().err
