"""Modelo de pose y escenario y carga de sus config.yaml (contrato config-pose-escenario.md)."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from src.errores import AssetInvalido

_NOMBRE_CARPETA = re.compile(r"^([PE])(\d+)(?:_(.+))?$")
# Poses de la v3: <vista>_<gesto>_<NN>, p. ej. frontal_neutro_01 o tres_cuartos_der_explicar_01.
# La vista puede llevar guiones bajos; el gesto no (puede llevar tildes, p. ej. señalar).
# <vista>_<gesto>_<NN> y, opcional, «_eye_contact» (la variante de 3/4 que mira a la cámara; se acepta «_eye_contacts» por si se escribe con s)
_NOMBRE_POSE_V3 = re.compile(r"^(?P<vista>.+?)_(?P<gesto>[^_]+)_(?P<nn>\d+)(?P<mirada>_eye_contacts?)?$")
MIRADAS = ("camara", "lateral")
TIPOS_GESTO = ("estado", "acento")
# Gestos de acento (breves: vuelven solos al reposo); el resto son estados
GESTOS_DE_ACENTO = frozenset({"pulgar", "señalar", "bienvenida", "contar"})
VISEMAS_FORMA = "ABCDEFGHX"


@dataclass(frozen=True)
class Ancla:
    x: float
    y: float
    ancho: float = 0.0
    angulo: float = 0.0


@dataclass(frozen=True)
class Anclas:
    boca: Ancla
    ojos: Ancla
    cabeza: Ancla


@dataclass(frozen=True)
class FormaBoca:
    """Calibración de UNA forma de boca en una pose (FR-062): centro del dibujo en el lienzo de la
    pose, escala (píxeles del lienzo por píxel del sprite), giro en grados (positivo = sentido
    horario, como en los calibradores) y reflejo propio de la forma."""
    x: float
    y: float
    s: float
    r: float = 0.0
    m: bool = False


@dataclass(frozen=True)
class Plano:
    alto_relativo: float
    centro_y_relativo: float = 0.33
    desenfoque: float = 0.0   # sigma en píxeles de salida


PLANOS_DEFECTO: Dict[str, Plano] = {
    "PL1": Plano(1.00, 0.33, 0), "PL2": Plano(0.75, 0.33, 1), "PL3": Plano(0.58, 0.33, 2),
    "PL4": Plano(0.42, 0.33, 4), "PL5": Plano(0.30, 0.33, 6), "PL6": Plano(0.18, 0.33, 9),
}


@dataclass(frozen=True)
class ParcheOjos:
    """Parpadeo por imagen (FR-040, T100): un recorte pequeño de la pose con los ojos cerrados (y otro a medio
    cerrar, si existe), con los bordes ya suavizados, que se pega sobre la pose abierta. (x, y) es la esquina
    superior izquierda del parche en el lienzo de la pose."""
    x: float
    y: float
    cerrado: Path
    medio: Optional[Path] = None


@dataclass(frozen=True)
class Movimiento:
    """Respiración y movimiento leve: apagados por defecto (el usuario los descartó por poco
    naturales). Se pueden activar por pose en config.yaml."""
    respiracion_escala: float = 0.0
    cabeza_px: float = 0.0


@dataclass(frozen=True)
class Pose:
    id: str
    nombre: str
    lienzo: Tuple[int, int]
    espejo: bool
    bocas_de: Optional[str]
    anclas: Anclas
    planos: Dict[str, Plano]
    movimiento: Movimiento
    ruta: Path
    respaldo: bool = False   # FR-083: imagen completa como capa base, toma fija
    ojos_de: Optional[str] = None   # reutiliza los ojos cerrados de otra pose (misma cara, con o sin gafas)
    # --- v3: poses por vista y gesto con calibración de boca por forma ---
    vista: str = ""
    gesto: str = ""
    tipo: str = ""                                   # "estado" o "acento"
    variante: int = 0
    formas: Optional[Dict[str, FormaBoca]] = None    # None = pose antigua con un solo ancla de boca
    pelo: Optional[Tuple[float, float]] = None       # centro de la cabeza (alineación en los cortes)
    parpadeo: bool = False
    parche_ojos: Optional[ParcheOjos] = None         # imágenes de parpadeo importadas (None = la pose no parpadea)
    mirada: str = "camara"                           # «camara» (mira al espectador) o «lateral» (3/4 sin contacto visual)
    cuenta: int = 0                                  # 1, 2, 3…: pose de «contar» (dedos levantados); el director la usa solo al contar, nunca al azar


def espejo_de_forma(pose: "Pose", visema: str) -> bool:
    """Reflejo efectivo de una forma (FR-051): el de la pose y el de la forma se combinan como un
    «o exclusivo»; con los dos activos la forma vuelve a su orientación original."""
    forma = (pose.formas or {}).get(visema)
    return bool(pose.espejo) != bool(forma.m if forma else False)


@dataclass(frozen=True)
class Escenario:
    id: str
    nombre: str
    planos_permitidos: Optional[Tuple[str, ...]]
    poses_permitidas: Optional[Tuple[str, ...]]
    peso: float
    ruta: Path

    def admite(self, pose_id: str, plano: str) -> bool:
        if self.poses_permitidas is not None and pose_id not in self.poses_permitidas:
            return False
        if self.planos_permitidos is not None and plano not in self.planos_permitidos:
            return False
        return True


def _id_y_nombre(carpeta: Path, prefijo: str) -> Tuple[str, str]:
    m = _NOMBRE_CARPETA.match(carpeta.name)
    if not m or m.group(1) != prefijo:
        raise AssetInvalido(
            f"El nombre de la carpeta «{carpeta.name}» no sigue la nomenclatura {prefijo}<n>[_nombre]",
            f"Renómbrala, por ejemplo {prefijo}1_nombre")
    return f"{prefijo}{m.group(2)}", m.group(3) or ""


def _leer_yaml(ruta: Path) -> dict:
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise AssetInvalido(f"El archivo {ruta.name} no es un YAML válido ({exc})",
                            f"Corrige la sintaxis de {ruta}") from exc
    if not isinstance(datos, dict):
        raise AssetInvalido(f"El archivo {ruta.name} debe contener un diccionario YAML",
                            "Revisa su formato con contracts/config-pose-escenario.md")
    return datos


def _id_pose_v3(carpeta: Path) -> Tuple[str, str, str, int]:
    m = _NOMBRE_POSE_V3.match(carpeta.name)
    if not m or not m.group("vista").strip() or " " in carpeta.name:
        raise AssetInvalido(
            f"El nombre de la carpeta «{carpeta.name}» no sigue la nomenclatura <vista>_<gesto>_<NN> "
            "(por ejemplo frontal_neutro_01 o tres_cuartos_der_explicar_01)",
            "Renómbrala con la vista, el gesto y el número de variante, sin espacios")
    return carpeta.name, m.group("vista"), m.group("gesto"), int(m.group("nn"))


def _formas(d: dict, id_pose: str, ruta: Path) -> Dict[str, FormaBoca]:
    crudas = d.get("formas")
    if not isinstance(crudas, dict) or not crudas:
        raise AssetInvalido(
            f"La pose {id_pose} no está calibrada: config.yaml no tiene «formas» de boca",
            "Calíbrala con el calibrador de bocas (prototipos/calibradores/Calibrador4/calibrador_34.html) e "
            "impórtala con `python -m src.biblioteca importar-poses --calibraciones <archivo.json>`")
    faltan = [v for v in VISEMAS_FORMA if v not in crudas]
    if faltan:
        raise AssetInvalido(
            f"Faltan formas de boca en la calibración de la pose {id_pose}: {', '.join(faltan)}",
            f"Calibra las 9 formas (A–H y X) y vuelve a importar la calibración en {ruta}")
    try:
        return {v: FormaBoca(float(crudas[v]["x"]), float(crudas[v]["y"]), float(crudas[v]["s"]),
                             float(crudas[v].get("r", 0.0)), bool(crudas[v].get("m", False)))
                for v in VISEMAS_FORMA}
    except (KeyError, TypeError, ValueError) as exc:
        raise AssetInvalido(f"Una forma de boca de la pose {id_pose} es inválida (necesita x, y y s numéricos)",
                            f"Revisa «formas» en {ruta}") from exc


def _parche_ojos(d: dict, id_pose: str, carpeta: Path) -> Optional[ParcheOjos]:
    pq = d.get("parpadeo")
    if not isinstance(pq, dict):
        return None
    try:
        x, y = float(pq["parche"]["x"]), float(pq["parche"]["y"])
        cerrado = carpeta / str(pq["cerrado"])
        medio = carpeta / str(pq["medio"]) if pq.get("medio") else None
    except (KeyError, TypeError, ValueError) as exc:
        raise AssetInvalido(f"El parpadeo de la pose {id_pose} es inválido en config.yaml (necesita parche.x, parche.y y cerrado)",
                            "Vuelve a importar el parpadeo con `importar-poses --parpadeos`") from exc
    for ruta in (cerrado, medio):
        if ruta is not None and not ruta.is_file():
            raise AssetInvalido(f"Falta la imagen de parpadeo {ruta.name} de la pose {id_pose}",
                                "Vuelve a importar el parpadeo con `importar-poses --parpadeos`")
    return ParcheOjos(x, y, cerrado, medio)


def _cargar_pose_v3(carpeta: Path, d: dict, cfg_ruta: Path) -> Pose:
    id_carpeta, vista, gesto, variante = _id_pose_v3(carpeta)
    if d.get("id") != id_carpeta:
        raise AssetInvalido(
            f"El id «{d.get('id')}» de config.yaml no coincide con la carpeta {carpeta.name} ({id_carpeta})",
            "Haz que el id y el nombre de la carpeta coincidan")
    tipo = str(d.get("tipo") or ("acento" if gesto in GESTOS_DE_ACENTO else "estado"))
    if tipo not in TIPOS_GESTO:
        raise AssetInvalido(f"El tipo «{tipo}» de la pose {id_carpeta} no es válido",
                            "Usa «estado» (puede mantenerse mucho tiempo) o «acento» (breve) en config.yaml")
    try:
        lienzo = (int(d["lienzo"][0]), int(d["lienzo"][1]))
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise AssetInvalido("Falta «lienzo» ([ancho, alto]) en config.yaml de la pose",
                            f"Añádelo en {cfg_ruta}") from exc
    formas = _formas(d, id_carpeta, cfg_ruta)
    a = formas["A"]
    # La cabeza (centro de la ventana de los planos) se deriva de la boca A salvo que config.yaml la fije
    try:
        cab = d["anclas"]["cabeza"]
        cabeza = Ancla(float(cab["x"]), float(cab["y"]))
    except (KeyError, TypeError, ValueError):
        cabeza = Ancla(a.x, a.y - 0.058 * lienzo[1])
    anclas = Anclas(Ancla(a.x, a.y), Ancla(cabeza.x, cabeza.y), cabeza)
    planos = dict(PLANOS_DEFECTO)
    for codigo, v in (d.get("planos") or {}).items():
        base = PLANOS_DEFECTO.get(codigo)
        if base is None:
            raise AssetInvalido(f"Plano desconocido «{codigo}» en config.yaml", "Usa PL1 a PL6")
        planos[codigo] = Plano(float(v.get("alto_relativo", base.alto_relativo)),
                               float(v.get("centro_y_relativo", base.centro_y_relativo)),
                               float(v.get("desenfoque", base.desenfoque)))
    mov = d.get("movimiento") or {}
    pelo = d.get("pelo")
    sufijo = _NOMBRE_POSE_V3.match(carpeta.name).group("mirada")
    mirada = str(d.get("mirada") or ("camara" if sufijo or not vista.startswith("tres_cuartos") else "lateral"))
    if mirada not in MIRADAS:
        raise AssetInvalido(f"La mirada «{mirada}» de la pose {id_carpeta} no es válida", "Usa «camara» o «lateral» en config.yaml")
    return Pose(id_carpeta, str(d.get("nombre") or f"{gesto} {variante:02d}"), lienzo, bool(d.get("espejo", False)),
                d.get("bocas_de"), anclas, planos,
                Movimiento(float(mov.get("respiracion_escala", 0.0)), float(mov.get("cabeza_px", 0.0))), carpeta,
                False, d.get("ojos_de"), vista, gesto, tipo, variante, formas,
                (float(pelo[0]), float(pelo[1])) if pelo else None, bool(d.get("parpadeo", False)),
                _parche_ojos(d, id_carpeta, carpeta), mirada, int(d.get("cuenta") or 0))


def _ancla(datos: dict, nombre: str, lienzo: Tuple[int, int], ruta: Path) -> Ancla:
    try:
        d = datos["anclas"][nombre]
        a = Ancla(float(d["x"]), float(d["y"]), float(d.get("ancho", 0)), float(d.get("angulo", 0)))
    except (KeyError, TypeError, ValueError) as exc:
        raise AssetInvalido(f"Falta o es inválida el ancla «{nombre}» en {ruta.name}",
                            f"Define anclas.{nombre} con x e y (o calíbrala con clics)") from exc
    if not (0 <= a.x < lienzo[0] and 0 <= a.y < lienzo[1]):
        raise AssetInvalido(
            f"El ancla «{nombre}» ({a.x:.0f}, {a.y:.0f}) queda fuera del lienzo {lienzo[0]}x{lienzo[1]}",
            f"Corrige sus coordenadas en {ruta}")
    return a


def cargar_pose(carpeta: Path) -> Pose:
    carpeta = Path(carpeta)
    cfg_ruta = carpeta / "config.yaml"
    if re.match(r"^P\d+(_|$)", carpeta.name) is None:
        # Nomenclatura de la v3 (<vista>_<gesto>_<NN>); un nombre inválido explica cómo corregirlo
        _id_pose_v3(carpeta)
        if not cfg_ruta.is_file():
            raise AssetInvalido(f"No se encontró config.yaml en {carpeta}",
                                "Importa la pose con `python -m src.biblioteca importar-poses`")
        return _cargar_pose_v3(carpeta, _leer_yaml(cfg_ruta), cfg_ruta)
    id_carpeta, nombre_carpeta = _id_y_nombre(carpeta, "P")
    if not cfg_ruta.is_file():
        raise AssetInvalido(f"No se encontró config.yaml en {carpeta}",
                            "Crea la configuración de la pose (ver contracts/config-pose-escenario.md)")
    d = _leer_yaml(cfg_ruta)
    if d.get("id") != id_carpeta:
        raise AssetInvalido(
            f"El id «{d.get('id')}» de config.yaml no coincide con la carpeta {carpeta.name} ({id_carpeta})",
            "Haz que el id y el nombre de la carpeta coincidan")
    try:
        lienzo = (int(d["lienzo"][0]), int(d["lienzo"][1]))
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise AssetInvalido("Falta «lienzo» ([ancho, alto]) en config.yaml de la pose",
                            f"Añádelo en {cfg_ruta}") from exc
    anclas = Anclas(*(_ancla(d, n, lienzo, cfg_ruta) for n in ("boca", "ojos", "cabeza")))
    planos = dict(PLANOS_DEFECTO)
    for codigo, v in (d.get("planos") or {}).items():
        base = PLANOS_DEFECTO.get(codigo)
        if base is None:
            raise AssetInvalido(f"Plano desconocido «{codigo}» en config.yaml", "Usa PL1 a PL6")
        planos[codigo] = Plano(float(v.get("alto_relativo", base.alto_relativo)),
                               float(v.get("centro_y_relativo", base.centro_y_relativo)),
                               float(v.get("desenfoque", base.desenfoque)))
    mov = d.get("movimiento") or {}
    movimiento = Movimiento(float(mov.get("respiracion_escala", 0.0)),
                            float(mov.get("cabeza_px", 0.0)))
    return Pose(id_carpeta, str(d.get("nombre") or nombre_carpeta), lienzo, bool(d.get("espejo", False)),
                d.get("bocas_de"), anclas, planos, movimiento, carpeta,
                bool(d.get("respaldo", False)), d.get("ojos_de"))


def cargar_escenario(carpeta: Path) -> Escenario:
    carpeta = Path(carpeta)
    id_carpeta, nombre = _id_y_nombre(carpeta, "E")
    d = {}
    cfg_ruta = carpeta / "config.yaml"
    if cfg_ruta.is_file():
        d = _leer_yaml(cfg_ruta)
        if d.get("id", id_carpeta) != id_carpeta:
            raise AssetInvalido(
                f"El id «{d.get('id')}» de config.yaml no coincide con la carpeta {carpeta.name}",
                "Haz que el id y el nombre de la carpeta coincidan")

    def _lista(clave):
        v = d.get(clave)
        return None if v is None else tuple(str(x) for x in v)

    return Escenario(id_carpeta, nombre, _lista("planos_permitidos"), _lista("poses_permitidas"),
                     float(d.get("peso", 1.0)), carpeta)
