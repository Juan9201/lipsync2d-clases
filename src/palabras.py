"""Cuándo se dice cada palabra del guion y dónde la clase cuenta algo («uno, dos, tres» / «primero, segundo, tercero»).

Rhubarb entrega formas de boca, no palabras. Las palabras se reparten sobre el audio con una estimación: cada una pesa por sus
sílabas y los puntos y comas del guion se anclan a las pausas reales de la voz (programación dinámica monótona), de modo que el
error no se acumula a lo largo de la clase. Es una estimación (≈ 0,2–0,4 s): basta para un gesto, no para una boca.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

_TOKEN = re.compile(r"\d+(?:st|nd|rd|th|º|ª)?|[^\W\d_]+(?:['’][^\W\d_]+)*|[.,;:!?…]")
_VOCALES = re.compile(r"[aeiouáéíóúüy]+", re.I)
_FUERTES = {".", "!", "?", "…", ";", ":"}
_PUNTOS = _FUERTES | {","}


@dataclass(frozen=True)
class Palabra:
    texto: str
    t0: float
    t1: float


@dataclass(frozen=True)
class Item:
    """Una palabra de la cuenta: n = 1, 2, 3…, dicha entre t0 y t1."""
    n: int
    t0: float
    t1: float
    palabra: str


def _peso(w: str) -> float:
    if w.isdigit():
        return 2.0
    return max(1, len(_VOCALES.findall(w))) + 0.35


def _tokens(texto: str) -> List[str]:
    return _TOKEN.findall(texto)


def _pausas_de_la_voz(cues, min_s: float = 0.18) -> Tuple[List[Tuple[float, float]], float, float]:
    """Pausas internas (X) de la voz, y el inicio y el fin del habla."""
    habla = [c for c in cues if c.valor != "X"]
    if not habla:
        return [], 0.0, 0.0
    ini, fin = habla[0].inicio, habla[-1].fin
    pausas, i = [], 0
    while i < len(cues):
        if cues[i].valor == "X":
            j = i
            while j + 1 < len(cues) and cues[j + 1].valor == "X":
                j += 1
            a, b = cues[i].inicio, cues[j].fin
            if a > ini and b < fin and b - a >= min_s:
                pausas.append((a, b))
            i = j + 1
        else:
            i += 1
    return pausas, ini, fin


def _emparejar(fracs_texto: Sequence[float], fuerza: Sequence[float], fracs_audio: Sequence[float], tol: float = 0.05):
    """Une (monótonamente) las pausas del guion con las de la voz: cada pareja cuesta la diferencia de posición relativa; omitir una
    pausa del texto o del audio también cuesta (menos si es una coma). Devuelve los pares (i_texto, j_audio)."""
    n, m = len(fracs_texto), len(fracs_audio)
    inf = float("inf")
    omitir_t = [0.004 + 0.012 * f for f in fuerza]
    omitir_a = 0.004
    c = np.full((n + 1, m + 1), inf)
    c[0, 0] = 0.0
    atras = {}
    for i in range(n + 1):
        for j in range(m + 1):
            if c[i, j] == inf:
                continue
            if i < n and c[i, j] + omitir_t[i] < c[i + 1, j]:
                c[i + 1, j] = c[i, j] + omitir_t[i]; atras[(i + 1, j)] = (i, j, False)
            if j < m and c[i, j] + omitir_a < c[i, j + 1]:
                c[i, j + 1] = c[i, j] + omitir_a; atras[(i, j + 1)] = (i, j, False)
            if i < n and j < m:
                d = abs(fracs_texto[i] - fracs_audio[j])
                if d <= tol and c[i, j] + d < c[i + 1, j + 1]:
                    c[i + 1, j + 1] = c[i, j] + d; atras[(i + 1, j + 1)] = (i, j, True)
    pares, k = [], (n, m)
    while k != (0, 0):
        i, j, unido = atras[k]
        if unido:
            pares.append((i, j))
        k = (i, j)
    return pares[::-1]


def tiempos_de_palabras(texto: str, cues, duracion_s: float) -> List[Palabra]:
    """Estima cuándo empieza y termina cada palabra del guion (los signos de puntuación no cuentan como palabras)."""
    toks = _tokens(texto)
    palabras = [t for t in toks if t not in _PUNTOS]
    if not palabras:
        return []
    pausas, ini, fin = _pausas_de_la_voz(cues)
    if fin <= ini:
        ini, fin = 0.0, max(duracion_s, 0.1)
    # posición (en peso acumulado) de cada palabra y de cada signo de puntuación
    acum, pesos, limites = 0.0, [], []                    # límites: (peso acumulado, fuerza)
    for t in toks:
        if t in _PUNTOS:
            if pesos:
                limites.append((acum, 1.0 if t in _FUERTES else 0.3))
        else:
            acum += _peso(t); pesos.append(_peso(t))
    total = acum
    if limites and limites[-1][0] >= total - 1e-9:
        limites = limites[:-1]
    ft = [w / total for w, _ in limites]
    fuerza = [f for _, f in limites]
    largo = fin - ini
    fa = [((a + b) / 2 - ini) / largo for a, b in pausas]
    pares = _emparejar(ft, fuerza, fa) if ft and fa else []
    # trozos entre pausas emparejadas: (peso_ini, peso_fin, t_ini, t_fin)
    trozos, w0, t0 = [], 0.0, ini
    for i, j in pares:
        a, b = pausas[j]
        trozos.append((w0, limites[i][0], t0, a))
        w0, t0 = limites[i][0], b
    trozos.append((w0, total, t0, fin))
    salida, acum = [], 0.0
    for w, p in zip(palabras, pesos):
        a, b = acum, acum + p
        acum = b
        k = next((x for x in trozos if (a + b) / 2 <= x[1] + 1e-9), trozos[-1])
        span = max(k[1] - k[0], 1e-9)
        f0, f1 = (max(a, k[0]) - k[0]) / span, (min(b, k[1]) - k[0]) / span
        salida.append(Palabra(w, k[2] + f0 * (k[3] - k[2]), k[2] + max(f1, f0) * (k[3] - k[2])))
    return salida


# ------------------------------------------------------------------ cuentas
_CARDINALES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
               "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}
_ORDINALES = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
              "firstly": 1, "secondly": 2, "thirdly": 3,
              "primero": 1, "primera": 1, "primer": 1, "segundo": 2, "segunda": 2, "tercero": 3, "tercera": 3, "tercer": 3,
              "cuarto": 4, "cuarta": 4, "quinto": 5, "quinta": 5, "sexto": 6, "sexta": 6}
_ROTULOS = {"number", "step", "rule", "tip", "reason", "point", "example", "way", "part", "lesson",
            "número", "numero", "paso", "regla", "consejo", "razón", "razon", "punto", "ejemplo", "forma", "parte", "lección"}
_CONECTORES = {"and", "then", "also", "now", "next", "finally", "y", "luego", "también", "ahora", "después", "finalmente", "por"}


def _numero_de(w: str) -> Optional[int]:
    k = w.lower()
    if k in _ORDINALES:
        return _ORDINALES[k]
    if k in _CARDINALES:
        return _CARDINALES[k]
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th|º|ª)?", k)
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 9 else None


def detectar_cuentas(texto: str, palabras: Sequence[Palabra], max_hueco: int = 40) -> List[List[Item]]:
    """Secuencias que cuentan «1, 2, (3…)» en orden, con cardinales u ordinales, en inglés o en español.
    Una palabra cuenta si abre una cláusula (tras un signo de puntuación o un conector) o la precede un rótulo («number», «paso»…);
    así «one second», «the two» o «uno de ellos» no activan el gesto. Cada secuencia empieza en 1 y exige al menos 1 y 2."""
    toks = _tokens(texto)
    candidatos, iw, previo, prev_p = [], -1, "", True
    for t in toks:
        if t in _PUNTOS:
            prev_p = True
            continue
        iw += 1
        n = _numero_de(t)
        if n is not None and iw < len(palabras):
            cardinal = t.lower() in _CARDINALES or t.isdigit()
            abre = prev_p or previo in _CONECTORES
            fuerte = (not cardinal) or previo in _ROTULOS        # ordinal o «number one»: vale aunque el siguiente número esté lejos
            if abre or (cardinal and previo in _ROTULOS):
                candidatos.append((iw, n, t, fuerte))
        previo, prev_p = t.lower(), False
    secuencias, actual = [], []
    for iw, n, t, fuerte in candidatos:
        if actual:
            hueco = iw - actual[-1][0]
            # un cardinal suelto («one week… two») solo cuenta si va pegado al siguiente («one, two, three»)
            if n == actual[-1][1] + 1 and hueco <= (max_hueco if fuerte and actual[-1][3] else 4):
                actual.append((iw, n, t, fuerte))
                continue
        if len(actual) >= 2:
            secuencias.append(actual)
        actual = [(iw, n, t, fuerte)] if n == 1 else []
    if len(actual) >= 2:
        secuencias.append(actual)
    return [[Item(n, palabras[iw].t0, palabras[iw].t1, t) for iw, n, t, _ in s] for s in secuencias]
