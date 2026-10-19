"""Prueba de video con un escenario hecho de CAPAS (fondo trasero + frente con transparencia), el director (poses y planos con zoom)
y la iluminación de la escena.

    .venv\\Scripts\\python.exe -I prototipos\\iluminacion\\video_capas.py <fondo_trasero.png> <frente.png> <audio.mp3> [segundos=20]
Escribe salidas/capas_<segundos>s.mp4 e imprime tiempos. La pared de detrás es provisional (las capas no traen pared)."""
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image, ImageFilter

sys.argv = [sys.argv[0], "x"] + sys.argv[1:]            # escena_escritorio lee argv[1] al importarse; aquí no se usa
import escena_escritorio as esc
from src import rutas
from src.animation import calcular_hablando, generar_parpadeos
from src.audio import convertir_para_analisis, info_audio
from src.biblioteca.modelos import cargar_pose
from src.director import cargar_reglas, dirigir
from src.encoder import Codificador
from src.layers.base import ContextoFrame
from src.layers.camara import Ventana
from src.layers.personaje import PersonajeLayer
from src.lipsync import analizar, cues_a_frames, suavizar
from src.render import _a_visemas
from src.timeline import LineaDeTiempo, semilla_de_clase

TRASERO, FRENTE, AUDIO = (Path(a) for a in sys.argv[2:5])
SEGUNDOS = float(sys.argv[5]) if len(sys.argv) > 5 else 20.0
FPS, SW, SH = 25, 3840, 2160                              # tamaño de la escena
W, H = 1280, 720                                          # tamaño del video
CABEZA_ESCENA = (2800.0, 800.0)                           # dónde se sienta el personaje (cabeza) en coordenadas de la escena
ESCALA_PJ = 0.80                                          # tamaño del personaje respecto a su lienzo de 3840x2160
Y_MESA = 1360                                             # borde trasero de la mesa en la escena
PLANOS = {"PL1": (1.00, 0.33), "PL2": (0.75, 0.33), "PL3": (0.58, 0.33), "PL4": (0.42, 0.33), "PL5": (0.30, 0.33)}
LUCES_ESCENA = [                                          # posición (x, y, altura) y alcance en píxeles de la escena
    {"pos": (1640, 520), "color": (1.00, 0.80, 0.55), "fuerza": 1.00, "alcance": 1300, "altura": 900},     # lámpara de escritorio
    {"pos": (1960, 1080), "color": (0.92, 0.88, 0.80), "fuerza": 0.45, "alcance": 1000, "altura": 500},   # pantalla del portátil
    {"pos": (3500, 860), "color": (1.00, 0.84, 0.60), "fuerza": 0.95, "alcance": 800, "altura": 300},     # lámpara del estante
]
AMBIENTE = np.array([0.30, 0.34, 0.34])
POSES = ["frontal_neutro_01", "frontal_neutro_02", "frontal_neutro_03", "frontal_explicar_01", "frontal_explicar_02", "frontal_pregunta_01"]


class Poses:                                              # lo mínimo que necesita el director de cada pose
    def __init__(self, pose):
        self.id, self.vista, self.gesto, self.tipo, self.variante = pose.id, pose.vista, pose.gesto, pose.tipo, pose.variante


def ventana_escena(plano: str, cabeza=CABEZA_ESCENA) -> Ventana:
    alto, centro = PLANOS[plano]
    h = alto * SH
    w = min(h * 16 / 9, SW)
    h = w * 9 / 16
    return Ventana(min(max(cabeza[0] - w / 2, 0), SW - w), min(max(cabeza[1] - centro * h, 0), SH - h), w, h)


def pared() -> Image.Image:
    y = np.linspace(0, 1, 720)[:, None, None]
    x = np.linspace(0, 1, 1280)[None, :, None]
    base = np.array([112, 134, 138], np.float32) * (1 - 0.30 * y) + np.array([150, 168, 168], np.float32) * 0.22 * (1 - y)
    arr = base * (1 - 0.22 * (((x - 0.5) * 1.5) ** 2 + ((y - 0.45) * 1.2) ** 2))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def relleno_bajo_mesa(frente: Image.Image) -> Image.Image:
    """Zona oscura bajo el tablero, entre las patas: el personaje está sentado y sus piernas no deben verse."""
    a = np.asarray(frente, dtype=np.float32)
    rgb, alfa = a[..., :3], a[..., 3]
    madera = (alfa > 200) & (rgb[..., 0] > rgb[..., 2] + 40) & (rgb[..., 0] > 120) & (rgb[..., 1] > 60)
    madera[:1250] = False
    relleno = np.zeros((SH, SW), bool)
    xs = np.where(madera.any(0))[0]
    for x in range(int(xs.min()), int(xs.max()) + 1):
        filas = np.where(madera[:, x])[0]
        if len(filas):
            relleno[filas.max() + 1:, x] = True
    relleno &= alfa < 10
    yy = np.mgrid[0:SH, 0:SW][0]
    sombra = np.zeros((SH, SW, 4), np.uint8)
    t = np.clip((yy - 1700) / 460.0, 0, 1)
    sombra[..., 0] = (22 - 14 * t).astype(np.uint8)
    sombra[..., 1] = (28 - 18 * t).astype(np.uint8)
    sombra[..., 2] = (30 - 20 * t).astype(np.uint8)
    sombra[..., 3] = (relleno * 255).astype(np.uint8)
    m = Image.fromarray(sombra[..., 3]).filter(ImageFilter.GaussianBlur(2.0))
    sombra_img = Image.fromarray(sombra, "RGBA")
    sombra_img.putalpha(m)
    return sombra_img


def recortar(img: Image.Image, v: Ventana) -> Image.Image:
    return img.resize((W, H), Image.LANCZOS, box=(v.x0, v.y0, v.x0 + v.w, v.y0 + v.h))


def main():
    t0 = time.perf_counter()
    cache = RAIZ / "cache"
    audio = cache / f"capas_{int(SEGUNDOS)}s.mp3"
    subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-t", str(SEGUNDOS), "-i", str(AUDIO), "-c", "copy", str(audio)], check=True)
    info = info_audio(audio)
    wav = cache / "analisis" / "capas.wav"
    convertir_para_analisis(audio, wav)
    res = analizar(wav, cache_dir=cache, reconocedor="phonetic")
    wav.unlink(missing_ok=True)
    frames = suavizar(cues_a_frames(res.cues, res.duracion_s, FPS))
    n = len(frames)
    visemas = _a_visemas(frames)
    poses_dir = RAIZ / "personajes" / "profesor" / "poses"
    poses = {pid: cargar_pose(poses_dir / pid) for pid in POSES}
    semilla = semilla_de_clase("capas", 0)
    reglas = cargar_reglas(None, {"toma_s": [4, 6], "cambio": {"prob_plano": 0.5}, "acentos": {"activo": False},
                                  "planos": {"permitidos": ["PL2", "PL3", "PL4", "PL5"], "inicial": "PL3"}})
    tomas = dirigir([Poses(p) for p in poses.values()], visemas, n, FPS, "E1", semilla, reglas, registro=print)
    lt = LineaDeTiempo(FPS, n, semilla, visemas, tomas, generar_parpadeos(n, FPS, semilla, cortes=[t.f0 for t in tomas]),
                       calcular_hablando(visemas, n))
    lt.validar()

    # --- escena: capas, pared y cámara por plano ---
    trasero = Image.open(TRASERO).convert("RGBA")
    frente = Image.open(FRENTE).convert("RGBA")
    sombra_mesa = relleno_bajo_mesa(frente)
    frente_total = sombra_mesa.copy()
    frente_total.alpha_composite(frente)
    pared_img = pared()
    usados = sorted({t.plano for t in tomas})
    v_escena = {pl: ventana_escena(pl) for pl in usados}
    base, delante = {}, {}
    for pl, v in v_escena.items():
        b = pared_img.resize((W, H), Image.LANCZOS, box=(v.x0 / SW * W, v.y0 / SH * H, (v.x0 + v.w) / SW * W, (v.y0 + v.h) / SH * H))
        b.alpha_composite(recortar(trasero, v))
        base[pl] = b
        delante[pl] = recortar(frente_total, v)

    # --- personaje: la ventana de cada plano en coordenadas del lienzo de la pose ---
    ref = next(iter(poses.values()))
    tx, ty = CABEZA_ESCENA[0] - ESCALA_PJ * ref.anclas.cabeza.x, CABEZA_ESCENA[1] - ESCALA_PJ * ref.anclas.cabeza.y
    v_pose = {pl: Ventana((v.x0 - tx) / ESCALA_PJ, (v.y0 - ty) / ESCALA_PJ, v.w / ESCALA_PJ, v.h / ESCALA_PJ) for pl, v in v_escena.items()}
    capa_pj = PersonajeLayer(poses, v_pose, (W, H))
    mapas = {}

    def mapas_de(pose_id, plano):
        if (pose_id, plano) not in mapas:
            v = v_escena[plano]
            k = W / v.w
            luces = [{**L, "pos": ((L["pos"][0] - v.x0) * k, (L["pos"][1] - v.y0) * k), "alcance": L["alcance"] * k, "altura": L["altura"] * k}
                     for L in LUCES_ESCENA]
            ctx0 = ContextoFrame(0, 0.0, (W, H), type("T", (), {"pose": pose_id, "plano": plano})(), "X", False, 1.0, 0.0, 0.0)
            fijo = componer_personaje(ctx0)
            mult, suma = esc.mapas_de_luz(fijo, luces, AMBIENTE, (Y_MESA - v.y0) * k, 250 * k, 22.0 * k / 0.62 * 0.5)
            ys, xs = np.where(np.asarray(fijo)[..., 3] > 0)
            caja = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else (0, 0, 1, 1)
            mapas[(pose_id, plano)] = (mult, suma, caja)
        return mapas[(pose_id, plano)]

    def componer_personaje(ctx):
        lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for c in capa_pj.renderizar(ctx):
            xa, ya = max(c.x, 0), max(c.y, 0)
            lienzo.alpha_composite(c.imagen.crop((xa - c.x, ya - c.y, min(c.x + c.imagen.width, W) - c.x, min(c.y + c.imagen.height, H) - c.y)), dest=(xa, ya))
        return lienzo

    prep = time.perf_counter() - t0
    final = RAIZ / "salidas" / f"capas_{int(SEGUNDOS)}s.mp4"
    t_bucle = time.perf_counter()
    with Codificador(final, audio, W, H, FPS, duracion_esperada_s=info.duracion_s) as enc:
        for i in range(n):
            previa, mezcla = lt.mezcla_en(i)
            ctx = ContextoFrame(i, i / FPS, (W, H), lt.toma_en(i), lt.visema_en(i), lt.parpadeando(i), 1.0, 0.0, 0.0, lt.fase_ojos(i), previa, mezcla)
            toma = lt.toma_en(i)
            pj = componer_personaje(ctx)
            mult, suma, (x0, y0, x1, y1) = mapas_de(toma.pose, toma.plano)
            iluminado = esc.aplicar_luz(pj.crop((x0, y0, x1, y1)), mult[y0:y1, x0:x1], suma[y0:y1, x0:x1])
            cuadro = base[toma.plano].copy()
            cuadro.alpha_composite(iluminado, dest=(x0, y0))
            cuadro.alpha_composite(delante[toma.plano])
            enc.escribir(cuadro.convert("RGB").tobytes())
    bucle = time.perf_counter() - t_bucle
    print(f"\n{n} frames ({n / FPS:.1f} s) · preparación {prep:.1f} s · bucle {bucle:.1f} s ({1000 * bucle / n:.0f} ms/frame) · {len(mapas)} mapas de luz")
    print(f"MP4 {final.stat().st_size / 1e6:.1f} MB · listo {final}")


if __name__ == "__main__":
    main()
