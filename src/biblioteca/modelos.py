"""Modelo de pose y escenario y carga de sus config.yaml (contrato config-pose-escenario.md)."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from src.errores import AssetInvalido

_NOMBRE_CARPETA = re.compile(r"^([PE])(\d+)(?:_(.+))?$")


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
class Plano:
    alto_relativo: float
    centro_y_relativo: float = 0.33
    desenfoque: float = 0.0   # sigma en píxeles de salida


PLANOS_DEFECTO: Dict[str, Plano] = {
    "PL1": Plano(1.00, 0.33, 0), "PL2": Plano(0.75, 0.33, 1), "PL3": Plano(0.58, 0.33, 2),
    "PL4": Plano(0.42, 0.33, 4), "PL5": Plano(0.30, 0.33, 6), "PL6": Plano(0.18, 0.33, 9),
}


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
    id_carpeta, nombre_carpeta = _id_y_nombre(carpeta, "P")
    cfg_ruta = carpeta / "config.yaml"
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
