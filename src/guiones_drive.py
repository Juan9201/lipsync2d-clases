"""Importa a `clases/` los guiones generados en Drive: un .txt por clase, con el nombre que deja el Apps Script
(`A1-M06-2 IA - <módulo> - <subtema>.txt`). En cada módulo la clase 1 la da una persona (HUMANO) y las 3 siguientes son de IA,
que son las que este proyecto renderiza. El texto se limpia de títulos de sección y marcas para que la voz solo lea el guion.

El id de la clase es el del nombre (`A1-M06-2`): importar de nuevo no duplica, solo actualiza el texto si cambió, y conserva los
ajustes que el usuario haya puesto a la clase (idioma, voz, escenarios, poses)."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from src.errores import ErrorAccionable
from src.ui import logica

NIVELES = ("A1", "A2", "B1", "B2")
IDIOMA_POR_NIVEL = {"A1": "mixto", "A2": "mixto", "B1": "en", "B2": "en"}      # A1/A2: explica en español con ejemplos en inglés
MIN_PALABRAS = 300                                                              # por debajo de esto no es una clase de 5 minutos

TITULOS = {"The Definition and Purpose", "The Spanish Equivalent", "Common Mistakes", "Practice Phrases",
           "Contexts and Examples of Use", "Precautions for Listening and Speaking", "Breaking the Rules and Verb Tenses",
           "Application in Past, Present, and Future"}
_NOMBRE = re.compile(r"^(A1|A2|B1|B2)-M(\d{2})-(\d)\s+(IA|HUMANO)\s+-\s+(.+)\.txt$")
_REVISAR = re.compile(r"\s*\(REVISAR[^)]*\)\s*$")
_RAYAS = re.compile(r"^\s*[-=_]{5,}\s*$")
_MARCAS = re.compile(r"\[[^\]]*\]")
_ENCABEZADO = re.compile(r"^\s*TEMA:")


@dataclass(frozen=True)
class FichaGuion:
    nivel: str
    modulo: int
    posicion: int
    humano: bool
    titulo: str
    revisar: bool
    ruta: Path

    @property
    def id_clase(self) -> str:
        return f"{self.nivel}-M{self.modulo:02d}-{self.posicion}"


def limpiar_guion(texto: str) -> str:
    """Solo el guion: sin rayas, títulos de sección, `[Text]`, cabeceras `TEMA:` ni formato markdown. Párrafos separados por una
    línea en blanco; el orden del texto no se toca (los títulos pueden venir desfasados, por eso no se usan)."""
    parrafos, actual = [], []
    for linea in texto.replace("\r\n", "\n").split("\n"):
        s = linea.strip()
        if not s or _RAYAS.match(s) or s in TITULOS or _ENCABEZADO.match(s):
            if actual:
                parrafos.append(" ".join(actual))
                actual = []
            continue
        s = _MARCAS.sub(" ", s).replace("**", "")
        s = re.sub(r"^#+\s*", "", s)
        s = " ".join(s.split())
        if s:
            actual.append(s)
    if actual:
        parrafos.append(" ".join(actual))
    return "\n\n".join(parrafos)


def leer_nombre(nombre: str) -> Optional[FichaGuion]:
    m = _NOMBRE.match(nombre)
    if not m:
        return None
    resto = m.group(5)
    return FichaGuion(nivel=m.group(1), modulo=int(m.group(2)), posicion=int(m.group(3)), humano=m.group(4) == "HUMANO",
                      titulo=_REVISAR.sub("", resto).strip(), revisar=bool(_REVISAR.search(resto)), ruta=Path(nombre))


def escanear(carpeta: Path, niveles: Optional[Iterable[str]] = None) -> List[FichaGuion]:
    """Los guiones con nombre reconocible bajo la carpeta (con o sin subcarpetas por nivel), en orden de curso."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise ErrorAccionable(f"No se encuentra la carpeta «{carpeta}»", "Revisa la ruta; si es de Drive, comprueba que `G:` esté montado")
    permitidos = set(niveles) if niveles else set(NIVELES)
    fichas = []
    for p in carpeta.rglob("*.txt"):
        f = leer_nombre(p.name)
        if f and f.nivel in permitidos:
            fichas.append(FichaGuion(f.nivel, f.modulo, f.posicion, f.humano, f.titulo, f.revisar, p))
    return sorted(fichas, key=lambda f: (NIVELES.index(f.nivel), f.modulo, f.posicion))


def importar_carpeta(raiz: Path, carpeta: Path, niveles: Optional[Iterable[str]] = None, solo_ia: bool = True) -> dict:
    """Crea o actualiza en `clases/` los guiones de la carpeta. Devuelve qué pasó con cada clase."""
    r = {"creadas": [], "actualizadas": [], "sin_cambios": [], "omitidas_humano": [], "ignoradas": [], "revisar": []}
    for f in escanear(carpeta, niveles):
        if f.humano and solo_ia:
            r["omitidas_humano"].append(f.id_clase)
            continue
        texto = limpiar_guion(f.ruta.read_text(encoding="utf-8", errors="replace"))
        palabras = len(texto.split())
        if palabras < MIN_PALABRAS:
            r["ignoradas"].append({"id": f.id_clase, "motivo": f"muy corto ({palabras} palabras; mínimo {MIN_PALABRAS})"})
            continue
        if f.revisar:
            r["revisar"].append(f.id_clase)
        existente = Path(raiz) / "clases" / f"{f.id_clase}.txt"
        if not existente.is_file():
            logica.guardar_clase(raiz, texto, f.id_clase, idioma=IDIOMA_POR_NIVEL[f.nivel], voz="colombiano")
            r["creadas"].append(f.id_clase)
        elif existente.read_text(encoding="utf-8").strip() == texto.strip():
            r["sin_cambios"].append(f.id_clase)
        else:
            logica.actualizar_clase(raiz, f.id_clase, texto=texto)                  # el texto cambió en Drive; los ajustes se quedan
            r["actualizadas"].append(f.id_clase)
    return r
