"""Configuración de un escenario con capas: `escenarios/E<n>_nombre/escena.yaml`.

    fondo: fondo.png | fondo.mp4     capa trasera (si trae transparencia, se pone una pared detrás)
    frente: frente.png               capa delantera con transparencia (mesa, objetos): tapa al personaje
    personaje: {cabeza: [x, y], escala: 0.8, ajustes: {pose: {dx, dy}}}     coordenadas de la escena
    mesa: {y: 1360}                  borde trasero de la mesa (la luz se atenúa al acercarse)
    luz: {activa, ambiente: [r, g, b], luces: [{nombre, pos: [x, y], color, fuerza, alcance, altura}]}
    poses_permitidas: [...]          vacío = todas"""
import copy
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import yaml
from PIL import Image

from src.errores import ErrorAccionable

ARCHIVO = "escena.yaml"
MAX_LUCES = 8
PARED_DEFECTO = {"arriba": [150, 168, 168], "abajo": [112, 134, 138]}


def config_defecto(lienzo: Tuple[int, int]) -> dict:
    w, h = lienzo
    return {
        "version": 1, "fondo": "", "frente": "", "pared": copy.deepcopy(PARED_DEFECTO),
        # punto de partida: personaje grande y alto, sentado a la derecha; el editor lo afina (escala 1 = lienzo de la pose, 3840 px)
        "personaje": {"cabeza": [round(w * 0.72), round(h * 0.28)], "escala": round(1.2 * w / 3840, 2), "ajustes": {}},
        "mesa": {"y": round(h * 0.63)},
        "luz": {"activa": True, "ambiente": [0.30, 0.34, 0.34], "luces": []},
        "poses_permitidas": [],
    }


def _fusionar(base: dict, cambios: dict) -> dict:
    for k, v in cambios.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("ajustes",):
            _fusionar(base[k], v)
        else:
            base[k] = v
    return base


def _numeros(valor, n: int, nombre: str, minimo: float, maximo: float) -> List[float]:
    if not isinstance(valor, (list, tuple)) or len(valor) != n or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in valor):
        raise ErrorAccionable(f"«{nombre}» debe ser una lista de {n} números", "Corrígelo en el editor de escenas")
    if not all(minimo <= x <= maximo for x in valor):
        raise ErrorAccionable(f"«{nombre}» tiene un valor fuera de rango ({minimo} a {maximo})", "Corrígelo en el editor de escenas")
    return [float(x) for x in valor]


def validar_config(cfg: dict, lienzo: Tuple[int, int]) -> dict:
    """Devuelve la configuración limpia o lanza un ErrorAccionable que nombra el valor malo."""
    w, h = lienzo
    p = cfg["personaje"]
    p["cabeza"] = _numeros(p["cabeza"], 2, "personaje.cabeza", -w, 2 * w)
    esc = p["escala"]
    if not isinstance(esc, (int, float)) or isinstance(esc, bool) or not 0.1 <= esc <= 3.0:
        raise ErrorAccionable("«personaje.escala» debe estar entre 0,1 y 3", "Usa un número, por ejemplo 0,8")
    p["escala"] = float(esc)
    if not isinstance(p["ajustes"], dict):
        raise ErrorAccionable("«personaje.ajustes» debe ser un diccionario por pose", "Revisa escena.yaml")
    p["ajustes"] = {str(k): {"dx": _numeros([v.get("dx", 0), v.get("dy", 0)], 2, f"ajuste de {k}", -w, w)[0],
                             "dy": _numeros([v.get("dx", 0), v.get("dy", 0)], 2, f"ajuste de {k}", -w, w)[1]}
                    for k, v in p["ajustes"].items() if isinstance(v, dict)}
    m = cfg["mesa"]
    if not isinstance(m.get("y"), (int, float)) or not 0 <= m["y"] <= h:
        raise ErrorAccionable("«mesa.y» debe estar dentro de la altura de la escena", "Arrastra la línea de la mesa en el editor")
    m["y"] = float(m["y"])
    luz = cfg["luz"]
    luz["activa"] = bool(luz.get("activa", True))
    luz["ambiente"] = _numeros(luz["ambiente"], 3, "luz.ambiente", 0, 2)
    if not isinstance(luz["luces"], list) or len(luz["luces"]) > MAX_LUCES:
        raise ErrorAccionable(f"Puede haber como máximo {MAX_LUCES} luces", "Quita alguna en el editor de escenas")
    limpias = []
    for i, L in enumerate(luz["luces"], 1):
        if not isinstance(L, dict):
            raise ErrorAccionable(f"La luz {i} no es válida", "Revisa escena.yaml")
        fuerza, alcance, altura = L.get("fuerza", 1.0), L.get("alcance", 800), L.get("altura", 400)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (fuerza, alcance, altura)):
            raise ErrorAccionable(f"La luz {i} tiene valores que no son números", "Revisa fuerza, alcance y altura")
        if not (0 <= fuerza <= 5 and 20 <= alcance <= 6000 and 10 <= altura <= 4000):
            raise ErrorAccionable(f"La luz {i} tiene fuerza, alcance o altura fuera de rango", "Fuerza 0–5, alcance 20–6000, altura 10–4000")
        limpias.append({"nombre": str(L.get("nombre", f"luz {i}"))[:40], "pos": _numeros(L.get("pos", [0, 0]), 2, f"luz {i}.pos", -w, 2 * w),
                        "color": _numeros(L.get("color", [1, 1, 1]), 3, f"luz {i}.color", 0, 1.5), "fuerza": float(fuerza),
                        "alcance": float(alcance), "altura": float(altura)})
    luz["luces"] = limpias
    pr = cfg["pared"]
    for k in ("arriba", "abajo"):
        pr[k] = [int(round(x)) for x in _numeros(pr[k], 3, f"pared.{k}", 0, 255)]
    if not isinstance(cfg["poses_permitidas"], list):
        raise ErrorAccionable("«poses_permitidas» debe ser una lista", "Revisa escena.yaml")
    cfg["poses_permitidas"] = [str(x) for x in cfg["poses_permitidas"]]
    return cfg


def archivos_de_capas(carpeta: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """(fondo trasero, frente) tal como están en la carpeta del escenario, si existen."""
    carpeta = Path(carpeta)
    fondo = next((carpeta / n for n in ("fondo.mp4", "fondo.png", "fondo.jpg") if (carpeta / n).is_file()), None)
    frente = carpeta / "frente.png" if (carpeta / "frente.png").is_file() else None
    return fondo, frente


def es_escena(carpeta: Path) -> bool:
    """Un escenario es «con capas» cuando tiene frente.png o escena.yaml."""
    carpeta = Path(carpeta)
    return (carpeta / "frente.png").is_file() or (carpeta / ARCHIVO).is_file()


def lienzo_de(carpeta: Path) -> Tuple[int, int]:
    fondo, frente = archivos_de_capas(carpeta)
    ref = frente or fondo
    if ref is None:
        raise ErrorAccionable(f"El escenario {Path(carpeta).name} no tiene capas", "Sube el fondo y el frente en la pestaña Escenarios")
    if ref.suffix.lower() == ".mp4":
        from src.layers.fondo_video import _sondear
        i = _sondear(ref)
        return i["ancho"], i["alto"]
    with Image.open(ref) as im:
        return im.size


def luces_detectadas(carpeta: Path, maximo: int = 3) -> List[dict]:
    """Primera propuesta de luces: los puntos más brillantes de la escena (lámparas, pantallas). Se ajustan a mano en el editor."""
    fondo, frente = archivos_de_capas(carpeta)
    capas = [c for c in (fondo, frente) if c is not None and c.suffix.lower() != ".mp4"]
    if not capas:
        return []
    with Image.open(capas[0]) as im:
        w, h = im.size
    base = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    for c in capas:
        with Image.open(c) as im:
            base.alpha_composite(im.convert("RGBA"))
    pequena = np.asarray(base.convert("RGB").resize((128, 72), Image.BOX), dtype=np.float32) / 255.0
    lum = pequena @ np.array([0.2126, 0.7152, 0.0722])
    salida, usada = [], lum.copy()
    for _ in range(maximo):
        y, x = np.unravel_index(int(np.argmax(usada)), usada.shape)
        if usada[y, x] < 0.80:
            break
        zona = pequena[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3].reshape(-1, 3).mean(0)
        color = (zona / max(zona.max(), 1e-3)).clip(0.4, 1.0)
        salida.append({"nombre": f"luz {len(salida) + 1}", "pos": [round((x + 0.5) / 128 * w), round((y + 0.5) / 72 * h)],
                       "color": [round(float(c), 2) for c in color], "fuerza": 1.0, "alcance": round(w * 0.30), "altura": round(w * 0.10)})
        usada[max(y - 9, 0):y + 10, max(x - 9, 0):x + 10] = 0
    return salida


def cargar_config(carpeta: Path) -> dict:
    """escena.yaml con lo que falte completado con valores por defecto; sin archivo, la configuración inicial con luces detectadas."""
    carpeta = Path(carpeta)
    lienzo = lienzo_de(carpeta)
    cfg = config_defecto(lienzo)
    ruta = carpeta / ARCHIVO
    if ruta.is_file():
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ErrorAccionable(f"{ARCHIVO} no es un YAML válido ({exc})", "Corrígelo o bórralo para empezar de nuevo") from exc
        if not isinstance(datos, dict):
            raise ErrorAccionable(f"{ARCHIVO} debe contener un diccionario", "Corrígelo o bórralo para empezar de nuevo")
        _fusionar(cfg, datos)
    else:
        cfg["luz"]["luces"] = luces_detectadas(carpeta)
    fondo, frente = archivos_de_capas(carpeta)
    cfg["fondo"], cfg["frente"] = fondo.name if fondo else "", frente.name if frente else ""
    cfg["lienzo"] = list(lienzo)
    return validar_config(cfg, lienzo)


def guardar_config(carpeta: Path, cfg: dict) -> dict:
    """Valida y guarda escena.yaml (de forma atómica). Devuelve la configuración limpia."""
    carpeta = Path(carpeta)
    lienzo = lienzo_de(carpeta)
    limpia = validar_config(_fusionar(config_defecto(lienzo), copy.deepcopy({k: v for k, v in cfg.items() if k not in ("lienzo",)})), lienzo)
    fondo, frente = archivos_de_capas(carpeta)
    limpia["fondo"], limpia["frente"] = fondo.name if fondo else "", frente.name if frente else ""
    destino = carpeta / ARCHIVO
    temporal = carpeta / (ARCHIVO + ".tmp")
    temporal.write_text(yaml.safe_dump(limpia, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporal.replace(destino)
    limpia["lienzo"] = list(lienzo)
    return limpia
