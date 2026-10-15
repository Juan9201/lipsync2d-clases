"""Separación del personaje (FR-080): máscara editable (FR-082), cuerpo con transparencia y
preparación única por pose (FR-084). La segmentación en sí corre en .venv-prep."""
from pathlib import Path
from typing import Callable, Optional, Tuple

from PIL import Image

from src import rutas
from src.biblioteca.config_pose import anclas_por_defecto, escribir_config_pose
from src.biblioteca.placeholders import crear_bocas_placeholder, crear_ojos_desde_imagen
from src.errores import AssetInvalido
from src.prep.entorno_prep import ejecutar_trabajador
from src.prep.formato import ajustar_16_9
from src.prep.respaldo import ResultadoPrep, _ancla

MODELO_DEFECTO = "birefnet-general"   # elegido en el spike S2: único sin huecos en lentes ni marcador

Segmentador = Callable[[Path, Path, str], None]


def segmentar_con_trabajador(original: Path, mascara_salida: Path, modelo: str,
                             raiz: Path = rutas.RAIZ) -> None:
    ejecutar_trabajador(["segmentar", str(original), str(mascara_salida), "--modelo", modelo], raiz)


def aplicar_mascara(rgb: Image.Image, mascara: Image.Image) -> Image.Image:
    """Devuelve la imagen RGBA que tiene la máscara como canal alfa."""
    if rgb.size != mascara.size:
        raise AssetInvalido(
            f"La máscara mide {mascara.size[0]}x{mascara.size[1]} y la imagen {rgb.size[0]}x{rgb.size[1]}: "
            "deben tener el mismo tamaño",
            "Edita mascara.png sin cambiar su tamaño (o exporta una máscara nueva)")
    rgba = rgb.convert("RGBA")
    rgba.putalpha(mascara.convert("L"))
    return rgba


def _imagen_base(carpeta_pose: Path) -> Path:
    ajustada = carpeta_pose / "base_16x9.png"
    return ajustada if ajustada.is_file() else carpeta_pose / "original.png"


def _escribir_cuerpo(carpeta_pose: Path, base: Path, mascara: Path) -> Tuple[int, int]:
    with Image.open(base) as im, Image.open(mascara) as m:
        cuerpo = aplicar_mascara(im.convert("RGB"), m)
    cuerpo.save(carpeta_pose / "cuerpo.png")
    return cuerpo.size


def preparar_pose_segmentada(imagen: Path, carpeta_pose: Path, id_pose: str,
                             boca: Optional[Tuple[float, ...]] = None,
                             ojos: Optional[Tuple[float, ...]] = None,
                             modelo: str = MODELO_DEFECTO, modo_formato: str = "recortar",
                             forzar: bool = False, con_placeholders: bool = True,
                             segmentador: Optional[Segmentador] = None,
                             salida: Tuple[int, int] = (1280, 720)) -> ResultadoPrep:
    carpeta_pose = Path(carpeta_pose)
    mascara_ruta = carpeta_pose / "mascara.png"
    if (not forzar and (carpeta_pose / "cuerpo.png").is_file() and mascara_ruta.is_file()
            and (carpeta_pose / "config.yaml").is_file()):
        return ResultadoPrep(False, [f"La pose {id_pose} ya estaba preparada; no se repite "
                                     "(usa --forzar para rehacerla)"])
    carpeta_pose.mkdir(parents=True, exist_ok=True)
    with Image.open(imagen) as origen:
        r = ajustar_16_9(origen.convert("RGB"), modo_formato, salida=salida)
    avisos = list(r.avisos)
    if r.modificada:
        base = carpeta_pose / "base_16x9.png"
        r.imagen.save(base)
    else:
        base = Path(imagen)
    if forzar or not mascara_ruta.is_file():
        (segmentador or segmentar_con_trabajador)(base, mascara_ruta, modelo)
    else:
        avisos.append("Se usa la máscara que ya existe (mascara.png); no se vuelve a segmentar")
    ancho, alto = _escribir_cuerpo(carpeta_pose, base, mascara_ruta)
    defecto = anclas_por_defecto(ancho, alto)
    anclas = {"boca": _ancla(boca, defecto["boca"]), "ojos": _ancla(ojos, defecto["ojos"]),
              "cabeza": defecto["cabeza"]}
    if forzar or not (carpeta_pose / "config.yaml").is_file():
        escribir_config_pose(carpeta_pose, id_pose, carpeta_pose.name.split("_", 1)[1]
                             if "_" in carpeta_pose.name else "", (ancho, alto), anclas)
        if boca is None or ojos is None:
            avisos.append("Anclas de boca y ojos provisionales: calibra la posición con clics "
                          "(o pásalas con --boca y --ojos)")
    if con_placeholders:
        if not (carpeta_pose / "bocas" / "A.png").is_file():
            crear_bocas_placeholder(carpeta_pose)
        if not (carpeta_pose / "ojos_cerrados.png").is_file():
            with Image.open(base) as im_base:
                crear_ojos_desde_imagen(im_base, anclas["ojos"]["x"], anclas["ojos"]["y"],
                                        max(int(anclas["ojos"]["ancho"]), 8), carpeta_pose / "ojos_cerrados.png")
        avisos.append("Se usan bocas y ojos placeholder; sustitúyelos por los definitivos "
                      "(ver assets/README.md)")
    return ResultadoPrep(True, avisos)


def reimportar_mascara(carpeta_pose: Path, ruta_mascara: Path) -> None:
    """FR-082: reemplaza mascara.png por una corregida a mano y regenera cuerpo.png."""
    carpeta_pose = Path(carpeta_pose)
    base = _imagen_base(carpeta_pose)
    if not base.is_file():
        raise AssetInvalido(f"No se encontró original.png en {carpeta_pose}",
                            "Importa la imagen de la pose con `python -m src.biblioteca importar`")
    with Image.open(ruta_mascara) as m:
        mascara = m.convert("L")
    with Image.open(base) as im:
        if im.size != mascara.size:
            raise AssetInvalido(
                f"La máscara mide {mascara.size[0]}x{mascara.size[1]} y la imagen {im.size[0]}x{im.size[1]}",
                "Edita la máscara exportada (mascara.png) sin cambiar su tamaño")
    mascara.save(carpeta_pose / "mascara.png")
    _escribir_cuerpo(carpeta_pose, base, carpeta_pose / "mascara.png")
