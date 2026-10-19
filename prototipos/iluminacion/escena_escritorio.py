"""Prueba de una escena de escritorio: recorta la mesa para que el personaje quede «sentado» detrás y le da una iluminación
coherente con las luces de la escena (lámpara de escritorio, lámpara del estante y ambiente oscuro verdoso).

    .venv\\Scripts\\python.exe -I prototipos\\iluminacion\\escena_escritorio.py <escritorio.webp> [pose]
Escribe en salidas/prueba_luz/: escritorio_capas.png (fondo · personaje · mesa) y escritorio_resultado.png (sin luz · con luz)."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from src.biblioteca.modelos import cargar_pose
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.personaje import PersonajeLayer
from src.timeline import Toma

ESCENA = Path(sys.argv[1])
POSE = sys.argv[2] if len(sys.argv) > 2 else "frontal_neutro_01"
W, H = 1280, 720
CABEZA = (985, 282)          # dónde queda la cabeza del personaje en la escena (sentado en la silla)
ESCALA = 0.70                # tamaño del personaje respecto a PL1
Y_BORDE_MESA = 523           # borde trasero de la mesa: lo que está por debajo tapa al personaje

# luces de la escena: posición (x, y), color, intensidad, alcance en píxeles
LUCES = [
    {"nombre": "lámpara de escritorio", "pos": (500, 340), "color": (1.00, 0.78, 0.52), "fuerza": 1.30, "alcance": 400, "altura": 230},
    {"nombre": "pantalla del portátil", "pos": (560, 470), "color": (0.90, 0.88, 0.80), "fuerza": 0.42, "alcance": 420, "altura": 110},
    {"nombre": "lámpara del estante", "pos": (1157, 292), "color": (1.00, 0.84, 0.60), "fuerza": 0.95, "alcance": 300, "altura": 60},
]
AMBIENTE = np.array([0.15, 0.24, 0.27])


def sobre_negro(img):
    base = Image.new("RGBA", img.size, (0, 0, 0, 255))
    base.alpha_composite(img)
    return base.convert("RGB")


def pared() -> Image.Image:
    """Pared oscura verdosa con el resplandor de las lámparas (la imagen de la escena trae solo los objetos)."""
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    base = np.array([34, 50, 54], dtype=np.float32) * (1 - 0.35 * y) + np.array([54, 72, 76], dtype=np.float32) * 0.25 * (1 - y)
    vineta = 1 - 0.38 * (((x - 0.5) * 1.5) ** 2 + ((y - 0.45) * 1.2) ** 2)
    arr = base * np.broadcast_to(vineta, (H, W, 1))
    yy, xx = np.mgrid[0:H, 0:W]
    for L in LUCES[:1] + LUCES[2:]:
        d2 = (xx - L["pos"][0]) ** 2 + (yy - L["pos"][1]) ** 2
        arr += (np.exp(-d2 / (2 * (L["alcance"] * 0.55) ** 2))[..., None] * np.array(L["color"]) * 38 * (L["fuerza"] / 1.5))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def separar_mesa(escena: Image.Image):
    """Divide la escena en lo que queda detrás del personaje y lo que queda delante (mesa, objetos y planta colgante)."""
    a = np.asarray(escena, dtype=np.float32)
    rgb, alfa = a[..., :3], a[..., 3]
    opaco = alfa > 8
    yy, xx = np.mgrid[0:H, 0:W]
    delante = np.zeros((H, W), bool)
    delante |= opaco & (xx < 760)                                       # lámpara, portátil, planta de la izquierda y mesa
    delante |= opaco & (xx >= 760) & (yy >= Y_BORDE_MESA)               # la mesa y lo que cuelga debajo
    delante |= opaco & (xx >= 770) & (xx <= 865) & (yy >= 472) & (yy <= 556)    # la taza
    verde = (rgb[..., 1] > rgb[..., 0] * 1.12) & (rgb[..., 1] > rgb[..., 2] * 1.04)
    delante |= opaco & verde & (xx >= 940) & (yy >= 466)                # hojas de la planta colgante
    delante |= opaco & (xx >= 1010) & (xx <= 1105) & (yy >= 512) & (yy <= 592)  # su maceta
    # hueco bajo la mesa: se rellena oscuro para que el torso no se vea a través (el personaje está sentado)
    madera = opaco & (rgb[..., 0] > rgb[..., 2] + 8) & (rgb[..., 0] < 150) & (yy >= 520) & (yy <= 690)
    relleno = np.zeros((H, W), bool)
    for x in range(40, 1196):
        filas = np.where(madera[:, x])[0]
        if len(filas):
            relleno[filas.max() + 1:, x] = True
    relleno &= ~opaco
    suave = lambda m: np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.9)), dtype=np.float32) / 255.0
    m_delante = suave(delante)
    delante_img = a.copy()
    delante_img[..., 3] = alfa * m_delante
    atras_img = a.copy()
    atras_img[..., 3] = alfa * (1 - m_delante)
    sombra = np.zeros((H, W, 4), np.float32)
    degradado = np.clip((yy - 560) / 160.0, 0, 1)
    sombra[..., 0] = 10 * (1 - degradado) + 3
    sombra[..., 1] = 14 * (1 - degradado) + 4
    sombra[..., 2] = 16 * (1 - degradado) + 5
    sombra[..., 3] = 255 * suave(relleno)
    hueco = Image.fromarray(sombra.astype(np.uint8), "RGBA")
    mesa = hueco.copy()
    mesa.alpha_composite(Image.fromarray(delante_img.astype(np.uint8), "RGBA"))
    return Image.fromarray(atras_img.astype(np.uint8), "RGBA"), mesa


def personaje_rgba() -> Image.Image:
    pose = cargar_pose(RAIZ / "personajes" / "profesor" / "poses" / POSE)
    ventana = ventana_plano(pose, "PL1")
    capa = PersonajeLayer({pose.id: pose}, ventana, (W, H))
    ctx = ContextoFrame(0, 0.0, (W, H), Toma(0, "E1", pose.id, "PL1"), "B", False, 1.0, 0.0, 0.0)
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for c in capa.renderizar(ctx):
        x0, y0 = max(c.x, 0), max(c.y, 0)
        lienzo.alpha_composite(c.imagen.crop((x0 - c.x, y0 - c.y, min(c.x + c.imagen.width, W) - c.x, min(c.y + c.imagen.height, H) - c.y)), dest=(x0, y0))
    esc = (W / pose.lienzo[0])
    cx, cy = pose.anclas.cabeza.x * esc, pose.anclas.cabeza.y * esc          # la cabeza en el lienzo PL1
    nuevo = lienzo.resize((round(W * ESCALA), round(H * ESCALA)), Image.LANCZOS)
    salida = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox, oy = round(CABEZA[0] - cx * ESCALA), round(CABEZA[1] - cy * ESCALA)
    salida.alpha_composite(nuevo, dest=(max(ox, 0), max(oy, 0)), source=(max(-ox, 0), max(-oy, 0)))
    return salida


def iluminar(pj: Image.Image) -> Image.Image:
    arr = np.asarray(pj, dtype=np.float32) / 255.0
    alb, alfa = arr[..., :3], arr[..., 3]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # relieve falso: la silueta suavizada hace de «volumen»; su gradiente da la orientación del contorno
    masc = Image.fromarray((alfa * 255).astype(np.uint8))
    altura = np.asarray(masc.filter(ImageFilter.GaussianBlur(22)), dtype=np.float32) / 255.0
    gy, gx = np.gradient(altura)
    n = np.stack([-gx * 14, -gy * 14, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    luz_total = np.zeros((H, W, 3), np.float32) + AMBIENTE
    for L in LUCES:
        lx, ly = L["pos"]
        v = np.stack([lx - xx, ly - yy, np.full_like(xx, L["altura"])], -1)
        dist = np.linalg.norm(v, axis=-1, keepdims=True)
        dirv = v / np.maximum(dist, 1e-3)
        difusa = np.clip((n * dirv).sum(-1, keepdims=True), 0, 1)
        caida = np.exp(-(dist[..., 0] ** 2) / (2 * (L["alcance"]) ** 2))[..., None]
        luz_total += np.array(L["color"], np.float32) * L["fuerza"] * caida * (0.25 + 0.75 * difusa)
    # oclusión de la mesa: lo que está cerca del borde de la mesa recibe menos luz
    oclusion = 1 - 0.42 * np.clip((yy - (Y_BORDE_MESA - 95)) / 95.0, 0, 1)
    luz_total *= oclusion[..., None]
    # la luz cambia sobre todo el brillo; su color se aplica a medias para que la piel y la ropa no se ensucien
    brillo_luz = (luz_total * np.array([0.30, 0.59, 0.11])).sum(-1, keepdims=True)
    tinte = luz_total / np.maximum(brillo_luz, 1e-4)
    lit = alb * brillo_luz * (1 + 0.65 * (tinte - 1))
    lit = lit / (1 + 0.30 * lit)                                        # compresión suave: el blanco no se quema
    lit = np.clip(lit * 1.22, 0, 1)
    # reborde cálido del lado de las lámparas
    borde = np.asarray(masc.filter(ImageFilter.GaussianBlur(4.5)), dtype=np.float32) / 255.0
    interior = np.asarray(masc.filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
    contorno = np.clip(interior - borde, 0, 1) * 3.5 * (alfa > 0.5)
    mira_luz = np.clip(sum(((np.stack([L["pos"][0] - xx, L["pos"][1] - yy], -1) / np.maximum(np.linalg.norm(np.stack([L["pos"][0] - xx, L["pos"][1] - yy], -1), axis=-1, keepdims=True), 1e-3)) * n[..., :2]).sum(-1) * L["fuerza"] * np.exp(-((xx - L["pos"][0]) ** 2 + (yy - L["pos"][1]) ** 2) / (2 * (L["alcance"] * 1.2) ** 2)) for L in LUCES), 0, None)
    lit = np.clip(lit + np.array([1.0, 0.82, 0.58]) * (contorno * np.clip(mira_luz, 0, 1.2) * 0.38)[..., None], 0, 1)
    return Image.fromarray((np.dstack([lit, alfa]) * 255).astype(np.uint8), "RGBA")


def main():
    escena = Image.open(ESCENA).convert("RGBA").resize((W, H))
    atras, mesa = separar_mesa(escena)
    fondo = pared()
    pj = personaje_rgba()
    pj_luz = iluminar(pj)

    def componer(personaje):
        base = fondo.copy()
        base.alpha_composite(atras)
        base.alpha_composite(personaje)
        base.alpha_composite(mesa)
        return base.convert("RGB")
    sin_luz, con_luz = componer(pj), componer(pj_luz)
    destino = RAIZ / "salidas" / "prueba_luz"
    destino.mkdir(parents=True, exist_ok=True)
    hoja = Image.new("RGB", (W * 2, H))
    hoja.paste(sin_luz, (0, 0))
    hoja.paste(con_luz, (W, 0))
    ImageDraw.Draw(hoja).text((8, 8), "sin luz (solo mesa recortada)", fill=(255, 255, 0))
    ImageDraw.Draw(hoja).text((W + 8, 8), "con iluminación de la escena", fill=(255, 255, 0))
    hoja.save(destino / "escritorio_resultado.png")
    con_luz.save(destino / "escritorio_con_luz.png")
    capas = Image.new("RGB", (W * 3, H))
    for i, im in enumerate((sobre_negro(Image.alpha_composite(fondo, atras)), sobre_negro(pj_luz), sobre_negro(mesa))):
        capas.paste(im, (i * W, 0))
    capas.save(destino / "escritorio_capas.png")
    print("listo", destino / "escritorio_resultado.png")


if __name__ == "__main__":
    main()
