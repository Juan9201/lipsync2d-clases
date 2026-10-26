"""Director automático (FR-044 a FR-046, FR-090 a FR-094): decide las tomas de la clase — pose, plano de la cámara
virtual y momento del corte — con reglas ajustables en `reglas_director.yaml` y azar sembrado, de modo que la misma
entrada y la misma semilla producen siempre las mismas tomas.

Cada corte cambia UN solo elemento:
- el plano (la cámara se acerca o se aleja un paso, mismo personaje: corte seco, sin salto de cabeza), o
- la pose (otra variante de reposo, otro gesto o una vista distinta: se mezcla `mezcla_frames` frames), o
- un acento (gesto breve de 3 a 6 s que vuelve solo al reposo, con una separación mínima entre acentos).
Los cortes caen en la pausa de la voz más cercana (tolerancia ±2 s, FR-054)."""
import copy
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import yaml

from src.errores import ErrorAccionable
from src.timeline import Toma, Visema

PLANOS_VALIDOS = ("PL1", "PL2", "PL3", "PL4", "PL5", "PL6")

REGLAS_DEFECTO: Dict[str, object] = {
    "toma_s": [6, 20],                      # segundos entre cortes (FR-044: de 6 a 20 s)
    "tolerancia_pausa_s": 2,                # cuánto se puede mover un corte para caer en una pausa de la voz
    "cambio": {"prob_plano": 0.5},          # probabilidad de que un corte cambie solo el plano
    "planos": {
        "permitidos": ["PL2", "PL3", "PL4", "PL5"],
        "inicial": "PL3",
        "paso_maximo": 1,                   # el plano cambia de a un paso (FR-090)
        "evitar_volver": 0.3,               # peso al volver al plano anterior (1 = sin preferencia; evita vaivenes A-B-A)
        "pesos": {"PL2": 1.0, "PL3": 3.0, "PL4": 3.0, "PL5": 1.5},
    },
    "reposo": {"activo": True, "mezcla_frames": 2},     # mezcla entre poses (0 = corte seco)
    "acentos": {"activo": True, "probabilidad": 0.5, "duracion_s": [3, 6], "separacion_min_s": 20},
    # poses 3/4 sin contacto visual (mirada «lateral»): se eligen poco y duran un instante; las que miran a cámara no tienen límite.
    # «desvio»: desde una pose con contacto visual (…_eye_contact) se aparta la mirada un momento (su gemela de lado) y se vuelve
    "mirada": {"lateral_max_s": 1, "peso_lateral": 0.25,
               "desvio": {"activo": True, "cada_s": [6, 14], "duracion_s": [0.5, 1.0]}},
}


# ---------------------------------------------------------------- reglas
def _fusionar(base: dict, cambios: dict) -> dict:
    for k, v in cambios.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _fusionar(base[k], v)
        else:
            base[k] = v
    return base


def _rango(r: dict, clave: str, ruta: str, minimo: float = 0.0) -> None:
    v = r
    for parte in clave.split("."):
        v = v[parte]
    ok = (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)
          and minimo <= v[0] <= v[1])
    if not ok:
        raise ErrorAccionable(f"En {ruta}, «{clave}» debe ser [mínimo, máximo] con 0 ≤ mínimo ≤ máximo (vale {v})",
                              f"Corrígelo, por ejemplo {clave.split('.')[-1]}: [6, 20]")


def _validar(r: dict, ruta: str) -> dict:
    _rango(r, "toma_s", ruta, 1)
    _rango(r, "acentos.duracion_s", ruta, 0.5)
    for clave, (lo, hi) in {"cambio.prob_plano": (0, 1), "acentos.probabilidad": (0, 1)}.items():
        v = r[clave.split(".")[0]][clave.split(".")[1]]
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise ErrorAccionable(f"En {ruta}, «{clave.split('.')[1]}» debe estar entre {lo} y {hi} (vale {v})",
                                  f"Escribe un número entre {lo} y {hi}")
    if not isinstance(r["reposo"]["mezcla_frames"], int) or r["reposo"]["mezcla_frames"] < 0:
        raise ErrorAccionable(f"En {ruta}, «mezcla_frames» debe ser un entero ≥ 0 (vale {r['reposo']['mezcla_frames']})",
                              "Usa 0 para cortar en seco o 2 para mezclar dos frames")
    if not isinstance(r["acentos"]["separacion_min_s"], (int, float)) or r["acentos"]["separacion_min_s"] < 0:
        raise ErrorAccionable(f"En {ruta}, «separacion_min_s» debe ser ≥ 0", "Escribe segundos, por ejemplo 20")
    if not isinstance(r["tolerancia_pausa_s"], (int, float)) or r["tolerancia_pausa_s"] < 0:
        raise ErrorAccionable(f"En {ruta}, «tolerancia_pausa_s» debe ser ≥ 0", "Escribe segundos, por ejemplo 2")
    m = r["mirada"]
    _rango(r, "mirada.desvio.cada_s", ruta, 1)
    _rango(r, "mirada.desvio.duracion_s", ruta, 0.2)
    if m["desvio"]["duracion_s"][1] > 3:
        raise ErrorAccionable(f"En {ruta}, la mirada desviada no puede durar más de 3 s (vale {m['desvio']['duracion_s'][1]})",
                              "Una mirada desviada natural dura medio segundo o un segundo: usa duracion_s: [0.5, 1.0]")
    if not isinstance(m["desvio"]["activo"], bool):
        raise ErrorAccionable(f"En {ruta}, «mirada.desvio.activo» debe ser true o false", "Escribe activo: true o activo: false")
    if not isinstance(m["lateral_max_s"], (int, float)) or m["lateral_max_s"] < 0:
        raise ErrorAccionable(f"En {ruta}, «lateral_max_s» debe ser ≥ 0 (vale {m['lateral_max_s']})",
                              "Escribe los segundos máximos de una pose sin contacto visual (por ejemplo 4) o 0 para no limitar")
    if not isinstance(m["peso_lateral"], (int, float)) or not 0 < m["peso_lateral"] <= 1:
        raise ErrorAccionable(f"En {ruta}, «peso_lateral» debe estar entre 0 (sin incluir) y 1 (vale {m['peso_lateral']})",
                              "Usa 1 para tratarlas igual que las que miran a cámara, o un valor bajo (0.25) para preferirlas poco")
    p = r["planos"]
    malos = [x for x in p["permitidos"] if x not in PLANOS_VALIDOS]
    if not p["permitidos"] or malos:
        raise ErrorAccionable(f"En {ruta}, los planos permitidos no son válidos: {', '.join(map(str, malos)) or '(vacío)'}",
                              "Usa PL1 a PL6")
    if p["inicial"] not in p["permitidos"]:
        raise ErrorAccionable(f"En {ruta}, el plano inicial {p['inicial']} debe estar entre los permitidos "
                              f"({', '.join(p['permitidos'])})", "Cambia «inicial» o añade ese plano a «permitidos»")
    if not isinstance(p["evitar_volver"], (int, float)) or not 0 <= p["evitar_volver"] <= 1:
        raise ErrorAccionable(f"En {ruta}, «evitar_volver» debe estar entre 0 y 1 (vale {p['evitar_volver']})",
                              "Usa 1 para no preferir ningún plano o un valor bajo para evitar los vaivenes entre dos planos")
    if not isinstance(p["paso_maximo"], int) or p["paso_maximo"] < 1:
        raise ErrorAccionable(f"En {ruta}, «paso_maximo» debe ser un entero ≥ 1", "Usa 1 para cambiar de plano de a un paso")
    return r


def cargar_reglas(ruta: Optional[Path] = None, cambios: Optional[dict] = None) -> dict:
    """Reglas por defecto, con lo que indique el archivo YAML encima (lo que no se indica conserva su valor) y,
    si se pasan, `cambios` (para pruebas)."""
    reglas = copy.deepcopy(REGLAS_DEFECTO)
    nombre = "las reglas por defecto"
    if ruta is not None:
        ruta = Path(ruta)
        nombre = ruta.name
        if not ruta.is_file():
            raise ErrorAccionable(f"No existe el archivo de reglas {ruta}", "Revisa la ruta o bórrala para usar las reglas por defecto")
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ErrorAccionable(f"{ruta.name} no es un YAML válido ({exc})", "Corrige la sintaxis del archivo de reglas") from exc
        if not isinstance(datos, dict):
            raise ErrorAccionable(f"{ruta.name} debe contener un diccionario YAML", "Usa claves como toma_s, planos, acentos")
        _fusionar(reglas, datos)
    if cambios:
        _fusionar(reglas, cambios)
    return _validar(reglas, nombre)


# ---------------------------------------------------------------- director
def _es_acento(p) -> bool:
    return getattr(p, "tipo", "") == "acento"


def _es_lateral(p) -> bool:
    return getattr(p, "mirada", "camara") == "lateral"


def _gemela_de_lado(p, por_id: dict):
    """La pose 3/4 sin sufijo que es la misma que una `..._eye_contact(s)` pero mirando de lado (None si no existe)."""
    base = re.sub(r"_eye_contacts?$", "", p.id)
    g = por_id.get(base)
    return g if base != p.id and g is not None and _es_lateral(g) else None


def _insertar_desvios(tomas: List[Toma], por_id: dict, pausas: List[int], n_frames: int, fps: int, escenario: str, semilla: int,
                      reglas: dict, admite: Callable[[str, str], bool], tol: int, log: Callable[[str], None]) -> List[Toma]:
    """Mirada desviada: dentro de una toma con una pose de contacto visual se pasa un instante (≤ 1 s) a su gemela de lado y se vuelve a la
    misma pose y plano, como quien aparta los ojos al hablar. Cae en una pausa de la voz si hay una cerca; nunca recién cortada la pose ni justo
    antes del siguiente corte. Usa su propio generador: no altera el resto de las decisiones del director."""
    desv = reglas["mirada"]["desvio"]
    if not desv["activo"]:
        return tomas
    rng = np.random.default_rng([int(semilla), 11])
    cada, dur_s = desv["cada_s"], desv["duracion_s"]
    ini_min, fin_min = round(1.5 * fps), round(1.0 * fps)
    mezcla_def = reglas["reposo"]["mezcla_frames"] if reglas["reposo"]["activo"] else 0
    proximo = round(rng.uniform(*cada) * fps)
    salida: List[Toma] = []
    for i, t in enumerate(tomas):
        fin = tomas[i + 1].f0 if i + 1 < len(tomas) else n_frames
        gemela = _gemela_de_lado(por_id[t.pose], por_id)
        if gemela is None or not admite(gemela.id, t.plano):
            salida.append(t)
            continue
        salida.append(t)
        inicio_toma = t.f0
        while True:
            dur = max(2, round(rng.uniform(*dur_s) * fps))
            lo, hi = max(proximo, inicio_toma + ini_min), fin - fin_min - dur
            if lo > hi:
                break
            cand = [x for x in pausas if lo <= x <= hi and abs(x - proximo) <= tol]
            g = min(cand, key=lambda x: abs(x - proximo)) if cand else lo
            salida.append(Toma(g, escenario, gemela.id, t.plano, mezcla_def))
            salida.append(Toma(g + dur, escenario, t.pose, t.plano, mezcla_def))
            log(f"desvío de mirada: frame {g} ({g / fps:.1f} s) - {t.pose} -> {gemela.id} durante {dur / fps:.1f} s y vuelve")
            proximo = g + dur + round(rng.uniform(*cada) * fps)
            inicio_toma = g + dur
    return salida


def dirigir(poses: Sequence, visemas: Sequence[Visema], n_frames: int, fps: int, escenario: str, semilla: int,
            reglas: Optional[dict] = None, admite: Optional[Callable[[str, str], bool]] = None,
            plano_inicial: Optional[str] = None, registro: Optional[Callable[[str], None]] = None) -> List[Toma]:
    """Devuelve las tomas de la clase. `poses`: objetos con `id`, `vista`, `gesto`, `tipo` ("estado" o "acento"); la
    primera es la pose de partida. `admite(pose, plano)` aplica las restricciones del escenario (FR-092)."""
    reglas = reglas or cargar_reglas(None)
    admite = admite or (lambda pose, plano: True)
    log = registro or (lambda _linea: None)
    rng = np.random.default_rng([int(semilla), 7])
    poses = list(poses)
    if not poses:
        raise ErrorAccionable("El director no tiene ninguna pose para elegir", "Indica al menos una pose")
    estados = [p for p in poses if not _es_acento(p)] or poses
    acentos = [p for p in poses if _es_acento(p)] if estados is not poses else []
    pl = reglas["planos"]
    permitidos = sorted(pl["permitidos"], key=PLANOS_VALIDOS.index)
    inicial = plano_inicial or pl["inicial"]
    if inicial not in permitidos:
        permitidos = sorted(set(permitidos) | {inicial}, key=PLANOS_VALIDOS.index)
    por_id = {p.id: p for p in poses}
    tol = round(reglas["tolerancia_pausa_s"] * fps)
    toma_min, toma_max = (round(s * fps) for s in reglas["toma_s"])
    ac = reglas["acentos"]
    acento_min, acento_max = (round(s * fps) for s in ac["duracion_s"])
    sep_acentos = round(ac["separacion_min_s"] * fps)
    lat_max = round(reglas["mirada"]["lateral_max_s"] * fps)         # 0 = sin límite
    peso_lat = reglas["mirada"]["peso_lateral"]
    peso_mirada = lambda p: peso_lat if _es_lateral(p) else 1.0
    mezcla = reglas["reposo"]["mezcla_frames"] if reglas["reposo"]["activo"] else 0
    pausas = sorted({v.f0 for v in visemas if v.v == "X" and v.f0 > 0})

    # --- toma inicial: la primera pose de reposo y el plano inicial, o la primera combinación que el escenario admita
    combinaciones = [(p, q) for p in estados for q in [inicial] + [x for x in permitidos if x != inicial]]
    arranque = next(((p, q) for p, q in combinaciones if admite(p.id, q)), None)
    if arranque is None:
        raise ErrorAccionable(
            f"El escenario {escenario} no admite ninguna combinación de pose y plano",
            "Revisa `poses_permitidas` y `planos_permitidos` de ese escenario o elige otro")
    pose, plano = arranque
    tomas = [Toma(0, escenario, pose.id, plano, 0)]
    usos = {p.id: 0 for p in poses}
    usos[pose.id] = 1
    log(f"toma 1: frame 0 (0.0 s) - pose {pose.id}, plano {plano} (inicio)")
    ultimo_acento = -10 ** 9
    plano_previo = None                                   # el plano que se dejó en el último cambio de cámara
    en_acento = False
    f = 0

    def cercana(objetivo: int, lo: int, hi: int) -> int:
        cand = [x for x in pausas if max(lo, objetivo - tol) <= x <= min(hi, objetivo + tol)]
        return min(cand, key=lambda x: abs(x - objetivo)) if cand else max(lo, min(objetivo, hi))

    while True:
        lateral = lat_max > 0 and _es_lateral(pose)
        if en_acento:
            lo, hi = f + acento_min, f + acento_max
        else:
            lo, hi = f + toma_min, f + toma_max + tol
        if lateral:                                                   # una pose sin contacto visual dura poco
            hi = min(hi, f + lat_max)
            lo = min(lo, max(f + 1, f + lat_max // 2))
        objetivo = int(rng.integers(lo, (hi if lateral or en_acento else f + toma_max) + 1))
        corte = cercana(objetivo, lo, hi)
        margen_fin = fps if lateral else (acento_min if en_acento else toma_min // 2)
        if corte >= n_frames - margen_fin or corte >= n_frames:
            break

        def planos_vecinos():
            i = permitidos.index(plano)
            vecinos = [permitidos[j] for j in range(max(0, i - pl["paso_maximo"]), min(len(permitidos), i + pl["paso_maximo"] + 1))
                       if j != i and admite(pose.id, permitidos[j])]
            return vecinos

        def poses_de_reposo():
            return [p for p in estados if p.id != pose.id and admite(p.id, plano)]

        def elegir(candidatas, peso):
            w = np.array([peso(c) for c in candidatas], dtype=float)
            return candidatas[int(rng.choice(len(candidatas), p=w / w.sum()))]

        quiere_plano = (not en_acento) and (not lateral) and rng.random() < reglas["cambio"]["prob_plano"]
        vecinos, reposo = planos_vecinos(), poses_de_reposo()
        if quiere_plano and vecinos:
            plano_nuevo = elegir(vecinos, lambda q: pl["pesos"].get(q, 1.0) * (pl["evitar_volver"] if q == plano_previo else 1.0))
            tomas.append(Toma(corte, escenario, pose.id, plano_nuevo, 0))
            log(f"toma {len(tomas)}: frame {corte} ({corte / fps:.1f} s) - plano {plano} -> {plano_nuevo} (cambio de cámara, misma pose {pose.id})")
            plano_previo, plano = plano, plano_nuevo
            f = corte
            continue
        if en_acento:                                              # el acento vuelve solo al reposo
            candidatas = reposo or [p for p in estados if admite(p.id, plano)]
            nueva = elegir(candidatas, lambda p: peso_mirada(p) / (1 + usos[p.id]) ** 2) if candidatas else None
            motivo = "vuelve al reposo tras el acento"
            en_acento = False
        else:
            posibles_acentos = [p for p in acentos if p.id != pose.id and admite(p.id, plano)]
            puede_acento = (ac["activo"] and posibles_acentos and corte - ultimo_acento >= sep_acentos
                            and n_frames - corte >= acento_max + toma_min and rng.random() < ac["probabilidad"])
            if puede_acento:
                nueva = elegir(posibles_acentos, lambda p: peso_mirada(p) / (1 + usos[p.id]) ** 2)
                motivo = "acento (gesto breve)"
                en_acento, ultimo_acento = True, corte
            elif reposo:
                nueva = elegir(reposo, lambda p: peso_mirada(p) / (1 + usos[p.id]) ** 2)
                motivo = "otra variante o gesto de reposo"
            else:
                nueva = None
        if nueva is None:                                           # una sola pose y un solo plano: no hay qué cambiar
            f = corte
            continue
        vieja = pose
        tomas.append(Toma(corte, escenario, nueva.id, plano, mezcla))
        usos[nueva.id] += 1
        log(f"toma {len(tomas)}: frame {corte} ({corte / fps:.1f} s) - pose {vieja.id} -> {nueva.id}, plano {plano} ({motivo})")
        pose = por_id[nueva.id]
        f = corte
    return _insertar_desvios(tomas, por_id, pausas, n_frames, fps, escenario, semilla, reglas, admite, tol, log)
