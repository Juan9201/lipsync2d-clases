"""Manifiesto de lote (FR-101, FR-066): un CSV con una fila por clase. Contrato en
specs/001-lipsync2d-fase1/contracts/manifiesto-lote.md."""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from src.errores import ErrorAccionable
from src.lote.cola import Cola, Trabajo

COLUMNAS = ["id", "guion", "audio", "personaje", "escenarios", "poses", "resolucion", "semilla", "tts", "genero", "idioma", "lote"]
IDIOMAS = ("es", "en", "mixto")
RESOLUCIONES = ("1280x720", "1920x1080")
ID_VALIDO = re.compile(r"^[\w\-]+$", re.UNICODE)
AUDIOS = (".mp3", ".wav")


@dataclass
class InformeManifiesto:
    filas: int = 0
    sin_audio: List[str] = field(default_factory=list)    # hay guion pero falta el audio
    sin_guion: List[str] = field(default_factory=list)    # hay audio pero falta el guion


def crear_manifiesto(carpeta: Path, personaje: str, lote: str, destino: Path,
                     poses: str = "", escenarios: str = "", idioma: str = "es") -> InformeManifiesto:
    """Escanea `carpeta` buscando <id>.txt (guion) y <id>.mp3 o .wav (audio)."""
    carpeta = Path(carpeta).resolve()
    guiones = {p.stem: p for p in carpeta.glob("*.txt")}
    audios = {p.stem: p for p in carpeta.iterdir() if p.suffix.lower() in AUDIOS}
    inf = InformeManifiesto()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for id_clase in sorted(set(guiones) | set(audios)):
            if id_clase not in audios:
                inf.sin_audio.append(id_clase)
            if id_clase not in guiones:
                inf.sin_guion.append(id_clase)
            w.writerow({"id": id_clase, "guion": str(guiones.get(id_clase, "")), "audio": str(audios.get(id_clase, "")),
                        "personaje": personaje, "escenarios": escenarios, "poses": poses,
                        "resolucion": "1280x720", "semilla": "", "tts": "gemini-studio", "genero": "", "idioma": idioma, "lote": lote})
            inf.filas += 1
    return inf


def escribir_manifiesto(filas: List[dict], destino: Path) -> Path:
    """Escribe un manifiesto con las columnas estándar a partir de filas ya armadas (por ejemplo desde la interfaz)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in COLUMNAS})
    return destino


def _existe(ruta: str, raiz: Path) -> bool:
    p = Path(ruta)
    return (p if p.is_absolute() else Path(raiz) / p).is_file()


def leer_manifiesto(ruta: Path, raiz: Path) -> List[Trabajo]:
    """Lee y valida el CSV. Si hay problemas los informa TODOS juntos, con el número de fila."""
    problemas: List[str] = []
    trabajos: List[Trabajo] = []
    vistos = set()
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for n, fila in enumerate(csv.DictReader(f), start=2):
            fila = {k: (v or "").strip() for k, v in fila.items() if k}
            id_clase = fila.get("id", "")
            if not id_clase or not ID_VALIDO.match(id_clase):
                problemas.append(f"fila {n}: el id «{id_clase}» no es válido (usa letras, números, _ y -)")
                continue
            if id_clase in vistos:
                problemas.append(f"fila {n}: el id «{id_clase}» está duplicado en el manifiesto")
                continue
            vistos.add(id_clase)
            guion, audio = fila.get("guion", ""), fila.get("audio", "")
            if not guion and not audio:
                problemas.append(f"fila {n} ({id_clase}): no tiene ni guion ni audio")
            for nombre, valor in (("guion", guion), ("audio", audio)):
                if valor and not _existe(valor, raiz):
                    problemas.append(f"fila {n} ({id_clase}): el {nombre} no existe: {valor}")
            resolucion = fila.get("resolucion") or "1280x720"
            if resolucion not in RESOLUCIONES:
                problemas.append(f"fila {n} ({id_clase}): resolución «{resolucion}» no válida (usa {' o '.join(RESOLUCIONES)})")
            idioma = (fila.get("idioma") or "es").lower()
            if idioma not in IDIOMAS:
                problemas.append(f"fila {n} ({id_clase}): el idioma «{idioma}» no es válido (usa {', '.join(IDIOMAS)})")
            semilla = fila.get("semilla", "")
            if semilla and not semilla.lstrip("-").isdigit():
                problemas.append(f"fila {n} ({id_clase}): la semilla «{semilla}» debe ser un número entero")
            trabajos.append(Trabajo(
                id=id_clase, lote=fila.get("lote", ""), personaje=fila.get("personaje") or "profesor",
                audio=audio or None, guion=guion or None, poses=fila.get("poses", ""),
                escenarios=fila.get("escenarios", ""), resolucion=resolucion,
                semilla=int(semilla) if semilla.lstrip("-").isdigit() and semilla else None,
                tts=fila.get("tts") or "gemini-studio", genero=fila.get("genero") or None, idioma=idioma))
    if problemas:
        raise ErrorAccionable(f"El manifiesto tiene {len(problemas)} problema(s):\n  " + "\n  ".join(problemas),
                              "Corrige las filas indicadas y vuelve a encolar")
    return trabajos


def encolar_manifiesto(cola: Cola, ruta: Path, raiz: Path) -> Tuple[int, List[str]]:
    return cola.encolar(leer_manifiesto(ruta, raiz))
