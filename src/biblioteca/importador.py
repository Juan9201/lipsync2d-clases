"""Importador de entrada/ (FR-064, FR-061): clasifica por nombre los archivos de assets, los
valida y los copia a la estructura de carpetas. No borra los originales."""
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from PIL import Image, UnidentifiedImageError

from src.biblioteca.config_pose import escribir_config_pose

IMAGENES = {".png", ".jpg", ".jpeg", ".webp"}
RE_BOCA = re.compile(r"^P(\d+)_boca_([A-HX])\.png$", re.IGNORECASE)
RE_OJOS = re.compile(r"^P(\d+)_ojos\.png$", re.IGNORECASE)
RE_POSE = re.compile(r"^P(\d+)(?:_(.+))?\.png$", re.IGNORECASE)
RE_ESCENARIO = re.compile(r"^E(\d+)(?:_(.+))?\.(png|jpg|jpeg|mp4)$", re.IGNORECASE)
EJEMPLO = "P3_explicando.png, P3_boca_A.png, P3_ojos.png o E2_salon.png"


@dataclass(frozen=True)
class Rechazo:
    archivo: str
    motivo: str


@dataclass
class InformeImportacion:
    importados: List[str] = field(default_factory=list)
    rechazados: List[Rechazo] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)


def _carpeta_pose(poses: Path, n: str, nombre: str, informe: InformeImportacion) -> Path:
    existente = next((d for d in sorted(poses.glob("P*")) if d.is_dir()
                      and re.match(rf"^P{n}(_|$)", d.name)), None) if poses.is_dir() else None
    deseada = poses / (f"P{n}_{nombre}" if nombre else f"P{n}")
    if existente is None:
        deseada.mkdir(parents=True, exist_ok=True)
        return deseada
    if nombre and existente.name == f"P{n}":
        existente.rename(deseada)     # las bocas llegaron antes que la imagen de la pose
        return deseada
    return existente


def _leer(ruta: Path):
    try:
        with Image.open(ruta) as im:
            return im.mode, im.size, (im.getchannel("A").getextrema()[0] if im.mode == "RGBA" else 255)
    except (UnidentifiedImageError, OSError):
        return None


def importar(entrada: Path, raiz: Path, personaje: str = "profesor") -> InformeImportacion:
    entrada, raiz = Path(entrada), Path(raiz)
    poses = raiz / "personajes" / personaje / "poses"
    informe = InformeImportacion()
    for archivo in sorted(entrada.iterdir()):
        es_video = archivo.suffix.lower() == ".mp4"
        if not archivo.is_file() or archivo.name.startswith(".") or (archivo.suffix.lower() not in IMAGENES and not es_video):
            continue
        nombre = archivo.name
        if es_video:                                  # escenario en video (FR-057): E<n>_nombre.mp4 -> fondo.mp4
            m = RE_ESCENARIO.match(nombre)
            if not m:
                informe.rechazados.append(Rechazo(
                    nombre, "los videos solo se admiten como escenarios y el nombre debe ser E<n>_nombre.mp4 "
                            "(por ejemplo E2_calle.mp4)"))
                continue
            carpeta = raiz / "escenarios" / (f"E{m.group(1)}_{m.group(2)}" if m.group(2) else f"E{m.group(1)}")
            carpeta.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archivo, carpeta / "fondo.mp4")
            informe.importados.append(f"{nombre} -> {(carpeta / 'fondo.mp4').relative_to(raiz)}")
            continue
        datos = _leer(archivo)
        if datos is None:
            informe.rechazados.append(Rechazo(nombre, "no se pudo leer como imagen; reexpórtala como PNG"))
            continue
        modo, tam, alfa_min = datos

        if (m := RE_BOCA.match(nombre)) or (m := RE_OJOS.match(nombre)):
            if modo != "RGBA":
                informe.rechazados.append(Rechazo(
                    nombre, f"debe ser PNG con transparencia (canal alfa) y es {modo}; "
                            "expórtalo como PNG RGBA con fondo transparente"))
                continue
            carpeta = _carpeta_pose(poses, m.group(1), "", informe)
            if m.re is RE_BOCA:
                destino = carpeta / "bocas" / f"{m.group(2).upper()}.png"
            else:
                destino = carpeta / "ojos_cerrados.png"
        elif m := RE_POSE.match(nombre):
            carpeta = _carpeta_pose(poses, m.group(1), m.group(2) or "", informe)
            if modo == "RGBA" and alfa_min < 255:
                destino = carpeta / "cuerpo.png"
                if not (carpeta / "config.yaml").is_file():
                    escribir_config_pose(carpeta, f"P{m.group(1)}", m.group(2) or "", tam)
                    informe.avisos.append(f"{nombre}: anclas provisionales; calibra boca y ojos con clics")
            else:
                destino = carpeta / "original.png"
                informe.avisos.append(
                    f"{nombre}: no tiene transparencia; prepárala con "
                    f"`python -m src.prep pose P{m.group(1)}` (segmentación) o con --respaldo")
        elif m := RE_ESCENARIO.match(nombre):
            carpeta = raiz / "escenarios" / (f"E{m.group(1)}_{m.group(2)}" if m.group(2) else f"E{m.group(1)}")
            destino = carpeta / f"fondo{archivo.suffix.lower().replace('.jpeg', '.jpg')}"
        else:
            informe.rechazados.append(Rechazo(
                nombre, f"el nombre no sigue la nomenclatura esperada (por ejemplo {EJEMPLO})"))
            continue

        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archivo, destino)
        informe.importados.append(f"{nombre} -> {destino.relative_to(raiz)}")
    return informe
