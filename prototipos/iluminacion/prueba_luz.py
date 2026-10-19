"""Prototipo de iluminación (no es parte del render): lee el fondo y le da al personaje su luz ambiente, una luz principal con
sombreado suave y un reborde de luz, para ver si «inmersión» es viable con este estilo de dibujo.

    .venv\\Scripts\\python.exe -I prototipos\\iluminacion\\prueba_luz.py [pose] [segundo_del_fondo]
Escribe salidas/prueba_luz/luz_<pose>.png con tres columnas: original · luz moderada · luz fuerte."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from src.biblioteca.modelos import cargar_pose
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.fondo_video import FondoVideoLayer
from src.layers.personaje import PersonajeLayer
from src.timeline import Toma

POSE = sys.argv[1] if len(sys.argv) > 1 else "frontal_neutro_01"
SEGUNDO = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
SALIDA = (960, 540)
PLANO = "PL3"


def luminancia(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def capas_a_rgba(capas):
    lienzo = Image.new("RGBA", SALIDA, (0, 0, 0, 0))
    for c in capas:
        x0, y0 = max(c.x, 0), max(c.y, 0)
        recorte = c.imagen.crop((x0 - c.x, y0 - c.y, min(c.x + c.imagen.width, SALIDA[0]) - c.x, min(c.y + c.imagen.height, SALIDA[1]) - c.y))
        lienzo.alpha_composite(recorte, dest=(x0, y0))
    return lienzo


def analizar_fondo(fondo_rgb):
    """Color ambiente (media ponderada), color de la luz principal (zona más brillante) y de qué lado viene."""
    a = np.asarray(fondo_rgb, dtype=np.float32) / 255.0
    lum = luminancia(a)
    ambiente = a.reshape(-1, 3).mean(0)
    umbral = np.percentile(lum, 90)
    brillantes = a[lum >= umbral]
    luz = brillantes.mean(0)
    h, w = lum.shape
    izq, der = lum[:, : w // 2].mean(), lum[:, w // 2:].mean()
    arriba, abajo = lum[: h // 2].mean(), lum[h // 2:].mean()
    # dirección hacia donde está la luz (x: derecha positiva, y: abajo positiva); se mezcla con una luz cenital suave
    dx = np.clip((der - izq) / max(lum.mean(), 1e-3) * 2.0, -1, 1)
    dy = np.clip((abajo - arriba) / max(lum.mean(), 1e-3) * 2.0, -1, 1) - 0.4
    d = np.array([dx, dy, 0.8])
    return ambiente, luz, d / np.linalg.norm(d), float(lum.mean())


def iluminar(pj: Image.Image, fondo_rgb: Image.Image, fuerza: float):
    ambiente, luz, direccion, brillo = analizar_fondo(fondo_rgb)
    arr = np.asarray(pj, dtype=np.float32) / 255.0
    rgb, alfa = arr[..., :3], arr[..., 3]
    # 1) luz ambiente: el color del fondo tiñe todo, más en las sombras que en las luces
    lum = luminancia(rgb)[..., None]
    tinte = 1.0 + (ambiente / max(ambiente.mean(), 1e-3) - 1.0) * (0.9 * fuerza)
    rgb = rgb * (1 - 0.5 * fuerza * (1 - lum)) + rgb * tinte * (0.5 * fuerza * (1 - lum))      # sombras
    rgb = rgb * (1 - 0.35 * fuerza) + rgb * tinte * (0.35 * fuerza)                          # todo
    # 2) exposición: un fondo oscuro oscurece un poco al personaje, uno claro lo aviva
    rgb = rgb * (1.0 + (brillo - 0.5) * 0.25 * fuerza)
    # 3) luz principal: relieve falso a partir de la silueta suavizada (borde = normal hacia afuera) y de los trazos oscuros del dibujo
    mascara = Image.fromarray((alfa * 255).astype(np.uint8))
    altura = np.asarray(mascara.filter(ImageFilter.GaussianBlur(26)), dtype=np.float32) / 255.0
    gy, gx = np.gradient(altura)
    nz = np.full_like(gx, 0.05)
    n = np.stack([-gx, -gy, nz], -1)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    difusa = np.clip((n * direccion).sum(-1), -1, 1)[..., None]
    rgb = rgb * (1.0 + difusa * 0.16 * fuerza) + (luz * 0.015 * fuerza) * np.clip(difusa, 0, 1)
    # 4) reborde: la luz del fondo envuelve el contorno del lado de la luz
    borde = np.asarray(mascara.filter(ImageFilter.GaussianBlur(5)), dtype=np.float32) / 255.0
    interior = np.asarray(mascara.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32) / 255.0
    contorno = np.clip(interior - borde, 0, 1) * 4.0 * (alfa > 0.5)
    lado = np.clip((n * np.array([direccion[0], direccion[1], 0.0])).sum(-1), 0, 1)
    rgb = rgb + (luz * 0.9)[None, None, :] * (contorno * lado * 0.35 * fuerza)[..., None]
    rgb = np.clip(rgb, 0, 1)
    salida = np.dstack([rgb, alfa])
    return Image.fromarray((salida * 255).astype(np.uint8), "RGBA"), (ambiente, luz, direccion)


def main():
    poses_dir = RAIZ / "personajes" / "profesor" / "poses"
    pose = cargar_pose(poses_dir / POSE)
    ventana = ventana_plano(pose, PLANO)
    ctx = ContextoFrame(round(SEGUNDO * 25), SEGUNDO, SALIDA, Toma(0, "E2", pose.id, PLANO), "B", False, 1.0, 0.0, 0.0)
    escenario = next((RAIZ / "escenarios").glob("E2_*")) / "fondo.mp4"
    with FondoVideoLayer(escenario, ventana, pose.lienzo, SALIDA, 25, desenfoque=pose.planos[PLANO].desenfoque,
                         cache_dir=RAIZ / "cache") as fondo:
        fondo.renderizar(ContextoFrame(0, 0.0, SALIDA, Toma(0, "E2", pose.id, PLANO), "X", False, 1.0, 0.0, 0.0))
        for n in range(1, round(SEGUNDO * 25)):                                       # avanza hasta el segundo pedido
            fondo.renderizar(ContextoFrame(n, n / 25, SALIDA, Toma(0, "E2", pose.id, PLANO), "X", False, 1.0, 0.0, 0.0))
        fondo_rgb = fondo.renderizar(ctx).imagen.convert("RGB")
    personaje = PersonajeLayer({pose.id: pose}, ventana, SALIDA)
    pj = capas_a_rgba(personaje.renderizar(ctx))
    columnas = []
    for etiqueta, fuerza in (("original", 0.0), ("luz moderada", 0.7), ("luz fuerte", 1.3)):
        if fuerza == 0:
            lit, info = pj, None
        else:
            lit, info = iluminar(pj, fondo_rgb, fuerza)
        base = fondo_rgb.convert("RGBA")
        base.alpha_composite(lit)
        im = base.convert("RGB")
        ImageDraw.Draw(im).text((8, 8), etiqueta, fill=(255, 255, 0))
        columnas.append(im)
        if info:
            ambiente, luz, d = info
    hoja = Image.new("RGB", (SALIDA[0] * 3, SALIDA[1]))
    for i, c in enumerate(columnas):
        hoja.paste(c, (i * SALIDA[0], 0))
    destino = RAIZ / "salidas" / "prueba_luz"
    destino.mkdir(parents=True, exist_ok=True)
    hoja.save(destino / f"luz_{POSE}.png")
    print("color ambiente", np.round(ambiente, 2), "luz", np.round(luz, 2), "dirección", np.round(d, 2))
    print("listo", destino / f"luz_{POSE}.png")


if __name__ == "__main__":
    main()
