"""Validación de assets antes de renderizar (FR-061): PNG con transparencia, bocas del
mismo tamaño, lienzo coherente. Los errores nombran el archivo y qué hacer."""
import logging
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError

from src.biblioteca.modelos import Pose, cargar_pose
from src.errores import AssetInvalido

VISEMAS = "ABCDEFGHX"
log = logging.getLogger("biblioteca")


def _abrir_png_rgba(ruta: Path, que: str) -> Tuple[int, int]:
    if not ruta.is_file():
        raise AssetInvalido(f"Falta el archivo {ruta.name} ({que})",
                            f"Súbelo a {ruta.parent} (ver assets/README.md)")
    try:
        with Image.open(ruta) as im:
            modo, tam = im.mode, im.size
    except (UnidentifiedImageError, OSError) as exc:
        raise AssetInvalido(f"No se pudo leer {ruta.name} como imagen ({exc})",
                            "Vuelve a exportarlo como PNG") from exc
    if modo != "RGBA":
        raise AssetInvalido(f"{ruta.name} debe ser PNG con transparencia (canal alfa), pero es {modo}",
                            "Expórtalo como PNG RGBA con fondo transparente")
    return tam


def _carpeta_de_pose(base: Pose, id_buscado: str, que: str = "las bocas") -> Path:
    for hermana in sorted(base.ruta.parent.iterdir()):
        if hermana.is_dir() and (hermana.name == id_buscado or hermana.name.startswith(id_buscado + "_")):
            return hermana
    raise AssetInvalido(
        f"La pose {base.id} reutiliza {que} de {id_buscado}, pero esa pose no existe",
        f"Crea la pose {id_buscado} o quita «{'ojos_de' if que == 'los ojos' else 'bocas_de'}» de "
        f"{base.ruta / 'config.yaml'}")


def carpeta_fuente_bocas(pose: Pose) -> Path:
    """Carpeta que contiene las bocas y los ojos de la pose (propia o la de `bocas_de`)."""
    return pose.ruta if not pose.bocas_de else _carpeta_de_pose(pose, pose.bocas_de)


def carpeta_fuente_ojos(pose: Pose) -> Path:
    """Carpeta con los ojos cerrados: la pose indicada en `ojos_de`, si no los propios y, a falta
    de estos, los de la pose de `bocas_de`. Una pose con gafas y otra sin gafas tienen ojos distintos."""
    if pose.ojos_de:
        return _carpeta_de_pose(pose, pose.ojos_de, "los ojos")
    if (pose.ruta / "ojos_cerrados.png").is_file():
        return pose.ruta
    return carpeta_fuente_bocas(pose)


def validar_pose(carpeta: Path) -> Pose:
    pose = cargar_pose(carpeta)
    tam_cuerpo = _abrir_png_rgba(pose.ruta / "cuerpo.png", "cuerpo de la pose")
    if tam_cuerpo != pose.lienzo:
        raise AssetInvalido(
            f"cuerpo.png mide {tam_cuerpo[0]}x{tam_cuerpo[1]} pero el lienzo de la pose es "
            f"{pose.lienzo[0]}x{pose.lienzo[1]} (tamaño distinto)",
            "Exporta el cuerpo con el tamaño del lienzo o corrige «lienzo» en config.yaml")
    fuente = carpeta_fuente_bocas(pose)
    _abrir_png_rgba(carpeta_fuente_ojos(pose) / "ojos_cerrados.png", "ojos cerrados")
    tamanos = {v: _abrir_png_rgba(fuente / "bocas" / f"{v}.png", f"boca {v}") for v in VISEMAS}
    referencia = tamanos["A"]
    for v, t in tamanos.items():
        if t != referencia:
            raise AssetInvalido(
                f"{v}.png mide {t[0]}x{t[1]} y A.png mide {referencia[0]}x{referencia[1]}: "
                "las 9 bocas deben tener el mismo tamaño",
                "Reexporta las bocas con el mismo tamaño de imagen")
    return pose


def validar_escenario(carpeta: Path, salida: Optional[Tuple[int, int]] = None) -> Path:
    carpeta = Path(carpeta)
    fondo = next((carpeta / n for n in ("fondo.png", "fondo.jpg") if (carpeta / n).is_file()), None)
    if fondo is None:
        raise AssetInvalido(f"Falta fondo.png en {carpeta.name}",
                            "Sube la imagen del escenario (ver assets/README.md)")
    try:
        with Image.open(fondo) as im:
            ancho, alto = im.size
    except (UnidentifiedImageError, OSError) as exc:
        raise AssetInvalido(f"No se pudo leer {fondo.name} como imagen ({exc})",
                            "Vuelve a exportarla como PNG o JPG") from exc
    if abs(ancho / alto - 16 / 9) > 0.01 * (16 / 9):
        raise AssetInvalido(f"El escenario mide {ancho}x{alto} y no es 16:9",
                            "Recórtalo o amplíalo a 16:9 (por ejemplo 3840x2160)")
    if salida and (ancho < salida[0] or alto < salida[1]):
        log.warning("El escenario %s (%dx%d) es menor que la salida %dx%d; se ampliará",
                    carpeta.name, ancho, alto, *salida)
    return fondo
