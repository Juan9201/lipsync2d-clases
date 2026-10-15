"""T091 (FR-057, FR-058): fondo en video con bucle y fundido de empalme, lectura en streaming,
plano sobre el video y casos de video corto, otra resolución u otra velocidad de fotogramas."""
import subprocess
import tracemalloc

import numpy as np
import pytest
from PIL import Image

from src import rutas
from src.errores import AssetInvalido
from src.layers.base import ContextoFrame
from src.layers.camara import Ventana

pytestmark = [pytest.mark.integracion,
              pytest.mark.skipif(not rutas.FFMPEG.exists(), reason="falta ffmpeg (ejecuta .\\instalar.ps1)")]

FPS = 25
SALIDA = (160, 90)
LIENZO = (320, 180)


def _ffmpeg(*args):
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", *args], check=True)


@pytest.fixture
def video_movil(proyecto_tmp):
    """3 s de un patrón que cambia en cada frame (testsrc2) a 25 fps, 160x90."""
    ruta = proyecto_tmp / "escenarios" / "E1_calle" / "fondo.mp4"
    ruta.parent.mkdir(parents=True)
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=160x90:rate={FPS}:duration=3", "-pix_fmt", "yuv420p", str(ruta))
    return ruta


def _ctx(n):
    return ContextoFrame(n_frame=n, t=n / FPS, salida=SALIDA, toma=None, visema="X", parpadeando=False,
                         escala=1.0, dx=0.0, dy=0.0)


def _frames_de(ruta, w, h):
    """Todos los frames de un video como arreglos RGB (solo para videos de prueba pequeños)."""
    r = subprocess.run([str(rutas.FFMPEG), "-v", "error", "-i", str(ruta), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    datos = np.frombuffer(r.stdout, np.uint8)
    return datos.reshape(-1, h, w, 3)


def _sonda(ruta):
    import json
    out = subprocess.run([str(rutas.FFPROBE), "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(ruta)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


# ---------------- el bucle ----------------
def test_la_unidad_de_bucle_dura_el_video_menos_el_fundido_y_no_tiene_audio(video_movil, proyecto_tmp):
    from src.layers.fondo_video import preparar_bucle
    destino = proyecto_tmp / "cache" / "bucle.mp4"
    n = preparar_bucle(video_movil, destino, fps=FPS, fundido_s=1.0)
    datos = _sonda(destino)
    video = next(s for s in datos["streams"] if s["codec_type"] == "video")
    assert not [s for s in datos["streams"] if s["codec_type"] == "audio"]
    assert video["r_frame_rate"] == "25/1" and video["pix_fmt"] == "yuv420p"
    assert n == pytest.approx((3.0 - 1.0) * FPS, abs=2)              # 3 s de video - 1 s de fundido
    assert int(video["nb_frames"]) == n


def test_el_empalme_del_bucle_no_da_salto_visible(video_movil, proyecto_tmp):
    from src.layers.fondo_video import preparar_bucle
    destino = proyecto_tmp / "cache" / "bucle.mp4"
    preparar_bucle(video_movil, destino, fps=FPS, fundido_s=1.0)
    f = _frames_de(destino, 160, 90).astype(int)
    entre_consecutivos = [np.abs(f[i + 1] - f[i]).mean() for i in range(len(f) - 1)]
    en_la_union = np.abs(f[0] - f[-1]).mean()                         # último frame -> primero del siguiente ciclo
    assert en_la_union <= 2.0 * np.median(entre_consecutivos)


def test_la_unidad_se_reutiliza_si_ya_existe(video_movil, proyecto_tmp):
    from src.layers.fondo_video import preparar_bucle
    destino = proyecto_tmp / "cache" / "bucle.mp4"
    preparar_bucle(video_movil, destino, fps=FPS, fundido_s=1.0)
    antes = destino.stat().st_mtime_ns
    preparar_bucle(video_movil, destino, fps=FPS, fundido_s=1.0)
    assert destino.stat().st_mtime_ns == antes


def test_video_mas_corto_que_el_fundido_reduce_el_fundido_y_avisa(proyecto_tmp, caplog):
    import logging
    from src.layers.fondo_video import preparar_bucle
    corto = proyecto_tmp / "corto.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=160x90:rate={FPS}:duration=1.5", "-pix_fmt", "yuv420p", str(corto))
    with caplog.at_level(logging.WARNING):
        n = preparar_bucle(corto, proyecto_tmp / "cache" / "b.mp4", fps=FPS, fundido_s=1.0)
    assert n >= FPS                                                    # queda al menos 1 s de bucle
    assert any("fundido" in r.getMessage().lower() for r in caplog.records)


def test_video_demasiado_corto_se_rechaza_con_mensaje_en_espanol(proyecto_tmp):
    from src.layers.fondo_video import preparar_bucle
    minimo = proyecto_tmp / "minimo.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=160x90:rate={FPS}:duration=0.4", "-pix_fmt", "yuv420p", str(minimo))
    with pytest.raises(AssetInvalido) as exc:
        preparar_bucle(minimo, proyecto_tmp / "cache" / "b.mp4", fps=FPS, fundido_s=1.0)
    assert "video" in str(exc.value).lower() and exc.value.sugerencia


def test_video_con_otra_velocidad_se_adapta_a_25_fps(proyecto_tmp):
    from src.layers.fondo_video import preparar_bucle
    v30 = proyecto_tmp / "v30.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=3", "-pix_fmt", "yuv420p", str(v30))
    destino = proyecto_tmp / "cache" / "b30.mp4"
    preparar_bucle(v30, destino, fps=FPS, fundido_s=1.0)
    assert next(s for s in _sonda(destino)["streams"] if s["codec_type"] == "video")["r_frame_rate"] == "25/1"


# ---------------- la capa ----------------
def test_la_capa_entrega_frames_del_tamano_de_salida_y_repite_el_ciclo(video_movil, proyecto_tmp):
    from src.layers.fondo_video import FondoVideoLayer
    with FondoVideoLayer(video_movil, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache") as capa:
        ciclo = capa.frames_por_ciclo
        frames = [capa.renderizar(_ctx(n)) for n in range(ciclo + 6)]
        assert frames[0].imagen.size == SALIDA and frames[0].imagen.mode == "RGBA" and (frames[0].x, frames[0].y) == (0, 0)
        assert frames[0].imagen.tobytes() != frames[5].imagen.tobytes()            # el fondo se mueve
        assert frames[3].imagen.tobytes() == frames[3 + ciclo].imagen.tobytes()    # y se repite tras un ciclo


def test_la_capa_lee_en_streaming_sin_acumular_frames(video_movil, proyecto_tmp):
    from src.layers.fondo_video import FondoVideoLayer
    with FondoVideoLayer(video_movil, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache") as capa:
        for n in range(20):
            capa.renderizar(_ctx(n))
        tracemalloc.start()
        for n in range(20, 80):
            capa.renderizar(_ctx(n))
        _, pico_60 = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        for n in range(80, 400):
            capa.renderizar(_ctx(n))
        _, pico_320 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert pico_320 - pico_60 < 1_000_000          # 5 veces más frames y la memoria no crece
        assert capa.procesos_lanzados == 1             # un solo decodificador, no uno por frame


def test_si_se_pide_un_frame_lejano_se_reposiciona(video_movil, proyecto_tmp):
    from src.layers.fondo_video import FondoVideoLayer
    with FondoVideoLayer(video_movil, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache") as capa:
        secuencial = [capa.renderizar(_ctx(n)).imagen.tobytes() for n in range(30)]
    with FondoVideoLayer(video_movil, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache") as otra:
        saltado = otra.renderizar(_ctx(25)).imagen.tobytes()
    a, b = np.frombuffer(secuencial[25], np.uint8).astype(int), np.frombuffer(saltado, np.uint8).astype(int)
    assert np.abs(a - b).mean() < 6                    # mismo contenido (con la pérdida del códec)


def test_el_plano_recorta_el_video_igual_que_una_imagen(proyecto_tmp):
    """FR-058: la ventana del plano sobre el video coincide con el mismo recorte sobre una imagen."""
    from src.layers.concretas import FondoLayer
    from src.layers.fondo_video import FondoVideoLayer
    base = Image.new("RGB", (320, 180))
    px = base.load()
    for y in range(180):
        for x in range(320):
            px[x, y] = (x * 255 // 319, y * 255 // 179, 128)
    png = proyecto_tmp / "ref.png"
    base.save(png)
    video = proyecto_tmp / "estatico.mp4"
    _ffmpeg("-loop", "1", "-i", str(png), "-t", "3", "-r", str(FPS), "-pix_fmt", "yuv420p", str(video))
    ventana = Ventana(80, 45, 160, 90)                 # zoom ×2 hacia el centro-izquierda
    esperado = FondoLayer(png, ventana, LIENZO, SALIDA, 0).renderizar(_ctx(0)).imagen.convert("RGB")
    with FondoVideoLayer(video, ventana, LIENZO, SALIDA, fps=FPS, fundido_s=0.5, cache_dir=proyecto_tmp / "cache") as capa:
        obtenido = capa.renderizar(_ctx(0)).imagen.convert("RGB")
    dif = np.abs(np.asarray(esperado).astype(int) - np.asarray(obtenido).astype(int)).mean()
    assert dif < 8


def test_video_de_otra_resolucion_se_ajusta_a_la_salida(proyecto_tmp):
    from src.layers.fondo_video import FondoVideoLayer
    grande = proyecto_tmp / "grande.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=640x360:rate={FPS}:duration=3", "-pix_fmt", "yuv420p", str(grande))
    with FondoVideoLayer(grande, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache") as capa:
        assert capa.renderizar(_ctx(0)).imagen.size == SALIDA


def test_la_capa_con_desenfoque_suaviza_el_fondo(video_movil, proyecto_tmp):
    from src.layers.fondo_video import FondoVideoLayer
    with FondoVideoLayer(video_movil, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache", desenfoque=0.0) as nitido:
        a = np.asarray(nitido.renderizar(_ctx(2)).imagen.convert("L")).astype(float)
    with FondoVideoLayer(video_movil, Ventana(0, 0, *LIENZO), LIENZO, SALIDA, fps=FPS, fundido_s=1.0,
                         cache_dir=proyecto_tmp / "cache", desenfoque=4.0) as borroso:
        b = np.asarray(borroso.renderizar(_ctx(2)).imagen.convert("L")).astype(float)
    assert np.abs(np.diff(b, axis=1)).mean() < np.abs(np.diff(a, axis=1)).mean()      # menos contraste local


# ---------------- el escenario en video en la biblioteca ----------------
def test_validar_escenario_acepta_un_video_16_9(video_movil):
    from src.biblioteca.validacion import validar_escenario
    assert validar_escenario(video_movil.parent) == video_movil


def test_validar_escenario_rechaza_un_video_que_no_es_16_9(proyecto_tmp):
    from src.biblioteca.validacion import validar_escenario
    carpeta = proyecto_tmp / "escenarios" / "E2_cuadrado"
    carpeta.mkdir(parents=True)
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=120x120:rate={FPS}:duration=2", "-pix_fmt", "yuv420p",
            str(carpeta / "fondo.mp4"))
    with pytest.raises(AssetInvalido) as exc:
        validar_escenario(carpeta)
    assert "16:9" in str(exc.value)


def test_el_importador_copia_un_escenario_en_video(video_movil, proyecto_tmp):
    from src.biblioteca.importador import importar
    entrada = proyecto_tmp / "entrada"
    (entrada / "E2_calle.mp4").write_bytes(video_movil.read_bytes())
    inf = importar(entrada, proyecto_tmp, "profe")
    assert not inf.rechazados
    assert (proyecto_tmp / "escenarios" / "E2_calle" / "fondo.mp4").is_file()


def test_el_importador_rechaza_un_video_que_no_es_un_escenario(video_movil, proyecto_tmp):
    from src.biblioteca.importador import importar
    entrada = proyecto_tmp / "entrada"
    (entrada / "P1_pose.mp4").write_bytes(video_movil.read_bytes())
    inf = importar(entrada, proyecto_tmp, "profe")
    assert any("E<n>_nombre.mp4" in r.motivo for r in inf.rechazados)
