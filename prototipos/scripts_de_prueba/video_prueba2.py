"""Prueba 2 (spike descartable): pose sin boca real (4K) + labios, con cámara virtual (plano) y audio real."""
import bisect, json, os, subprocess, sys, time
from pathlib import Path
from PIL import Image

RAIZ = Path(r"C:\Users\Juan 02\Desktop\Fase 1\Temp Real Assest Testing")
SP = Path(__file__).parent
DATOS = json.load(open(SP / "s1" / "sphinx_dialogo.json"))
CUES, DUR = DATOS["mouthCues"], DATOS["metadata"]["duration"]
AUDIO = RAIZ / "tts_008.mp3"
FPS, W, H = 25, 1280, 720

escena = Image.open(RAIZ / "Clean" / "sin boca.png").convert("RGB")      # 3840x2160

# Sprites: recorte a la caja de contenido (en el lienzo 3840x2160 de los sprites)
CAJA_S = (969, 564, 2880, 1637)
ANCLA_S = (1914, 1000)               # centro de los labios en el lienzo del sprite
BOCA_4K = (3092, 596)                # centro de la boca en la escena 4K
ESC_4K = float(os.environ.get("ESC", "0.069"))   # tamaño de los labios respecto al sprite original


def preparar(nombre, ventana):
    x0, y0, x1, y1 = ventana
    vista = escena.resize((W, H), Image.LANCZOS, box=ventana).convert("RGBA")
    k = W / (x1 - x0)                                    # escala escena->vista
    s = ESC_4K * k                                       # escala sprite->vista
    cx, cy = (BOCA_4K[0] - x0) * k, (BOCA_4K[1] - y0) * k
    cuadros = {}
    for v in "ABCDEFGH":
        im = Image.open(RAIZ / "Clean" / "8 shapes solo labios" / f"P1_boca_{v}.png").convert("RGBA").crop(CAJA_S)
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        fr = vista.copy()
        fr.alpha_composite(im, (round(cx - (ANCLA_S[0] - CAJA_S[0]) * s), round(cy - (ANCLA_S[1] - CAJA_S[1]) * s)))
        cuadros[v] = fr.convert("RGB").tobytes()
    cuadros["X"] = cuadros["A"]
    return cuadros


def visemas():
    n = int(DUR * FPS)
    starts = [c["start"] for c in CUES]
    vis = [CUES[max(bisect.bisect_right(starts, (i + 0.5) / FPS) - 1, 0)]["value"] for i in range(n)]
    i = 0
    while i < n:                                          # mínimo 2 frames (salvo A/X)
        j = i
        while j < n and vis[j] == vis[i]:
            j += 1
        if j - i < 2 and vis[i] not in "AX" and i > 0:
            vis[i:j] = [vis[i - 1]] * (j - i)
        i = j
    return vis


def renderizar(nombre, ventana):
    vis = visemas()
    cuadros = preparar(nombre, ventana)
    salida, parcial = RAIZ / f"{nombre}.mp4", RAIZ / f"{nombre}.part.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(AUDIO), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy",
           "-t", f"{DUR:.3f}", "-movflags", "+faststart", str(parcial)]
    t = time.perf_counter()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for v in vis:
        p.stdin.write(cuadros[v])
    p.stdin.close(); p.wait()
    os.replace(parcial, salida)
    print(f"{nombre}: {time.perf_counter() - t:.1f} s -> {salida}")
    return cuadros


if __name__ == "__main__":
    # Plano busto (PL4): ventana 16:9 de 900 px de alto, pegada al borde derecho
    busto = (2240, 150, 3840, 1050)
    c = renderizar("prueba2_busto", busto)
    renderizar("prueba2_completo", (0, 0, 3840, 2160))
    # fotogramas de control del busto: A, D, E, F
    from PIL import Image as I
    hoja = I.new("RGB", (640 * 4, 360))
    for k, v in enumerate("ADEF"):
        im = I.frombytes("RGB", (W, H), c[v]).crop((380, 90, 1020, 450))
        hoja.paste(im, (k * 640, 0))
    hoja.save(RAIZ / "_prueba2_control.png")
