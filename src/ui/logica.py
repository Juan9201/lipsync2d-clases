"""Lógica de la interfaz web local (FR-064, FR-071): guiones, voces, render y lote. Sin HTTP aquí: el servidor solo
traduce peticiones a estas funciones, así se prueban sin navegador.

Los guiones viven en `clases/<id>.txt` con sus ajustes (idioma, género de la voz, escenarios y poses permitidos) en
`clases/<id>.json`. Las voces que eliges se guardan en `tts_usuario.yaml`, que manda sobre `tts.yaml` sin tocarlo."""
import dataclasses
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src import rutas
from src.audio import SIN_VENTANA
from src.errores import ErrorAccionable

ID_VALIDO = re.compile(r"^[A-Za-z0-9_\-]{1,60}$")
IDIOMAS = ("es", "en", "mixto")
GENEROS = ("hombre", "mujer")
CODIGO_IDIOMA = {"es": "es-419", "en": "en-US"}                  # idioma que se pide a la webapp de voz
TEXTO_MUESTRA = {"es": "Hola, bienvenidos a la clase de hoy. Vamos a aprender algo nuevo.",
                 "en": "Hello, and welcome to today's class. Let's learn something new."}
CAMPOS_CLASE = ("idioma", "genero", "escenarios", "poses")


# ---------------------------------------------------------------- guiones
def _carpeta(raiz: Path) -> Path:
    return Path(raiz) / "clases"


def _validar_id(id_clase: str) -> str:
    if not isinstance(id_clase, str) or not ID_VALIDO.match(id_clase):
        raise ErrorAccionable(f"El identificador «{id_clase}» no es válido",
                              "Usa solo letras, números, guion y guion bajo (hasta 60 caracteres)")
    return id_clase


def _leer_meta(raiz: Path, id_clase: str) -> dict:
    ruta = _carpeta(raiz) / f"{id_clase}.json"
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    except (ValueError, OSError):
        datos = {}
    return {"idioma": datos.get("idioma", "es"), "genero": datos.get("genero", "hombre"),
            "escenarios": datos.get("escenarios", ""), "poses": datos.get("poses", "")}


def _escribir_meta(raiz: Path, id_clase: str, meta: dict) -> None:
    (_carpeta(raiz) / f"{id_clase}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def _validar_campos(campos: dict) -> dict:
    limpio = {}
    if "idioma" in campos:
        if campos["idioma"] not in IDIOMAS:
            raise ErrorAccionable(f"El idioma «{campos['idioma']}» no es válido", f"Usa {', '.join(IDIOMAS)}")
        limpio["idioma"] = campos["idioma"]
    if "genero" in campos:
        if campos["genero"] not in GENEROS:
            raise ErrorAccionable(f"El género «{campos['genero']}» no es válido", f"Usa {' o '.join(GENEROS)}")
        limpio["genero"] = campos["genero"]
    for k in ("escenarios", "poses"):
        if k in campos:
            limpio[k] = str(campos[k] or "").strip()
    return limpio


def _ficha(raiz: Path, id_clase: str) -> dict:
    carpeta = _carpeta(raiz)
    texto = (carpeta / f"{id_clase}.txt").read_text(encoding="utf-8", errors="replace")
    palabras = len(texto.split())
    videos = sorted((Path(raiz) / "salidas").glob(f"{id_clase}_*.mp4"), key=lambda p: p.stat().st_mtime)
    videos = [v for v in videos if not v.name.endswith(".part.mp4")]
    audio = next((carpeta / f"{id_clase}{e}" for e in (".mp3", ".wav") if (carpeta / f"{id_clase}{e}").is_file()), None)
    return {"id": id_clase, **_leer_meta(raiz, id_clase), "palabras": palabras, "minutos": round(palabras / 140, 1),
            "vista_previa": " ".join(texto.split())[:140], "audio": audio.name if audio else None,
            "video": videos[-1].name if videos else None}


def _ficha_de(raiz: Path, id_clase: str) -> dict:
    """La ficha de una clase que debe existir; si no, un error con la acción a seguir."""
    _validar_id(id_clase)
    if not (_carpeta(raiz) / f"{id_clase}.txt").is_file():
        raise ErrorAccionable(f"No existe la clase «{id_clase}»", "Actualiza la lista o crea la clase primero")
    return _ficha(raiz, id_clase)


def listar_clases(raiz: Path) -> List[dict]:
    carpeta = _carpeta(raiz)
    if not carpeta.is_dir():
        return []
    return [_ficha(raiz, p.stem) for p in sorted(carpeta.glob("*.txt")) if ID_VALIDO.match(p.stem)]


def siguiente_id(raiz: Path) -> str:
    usados = {p.stem for p in _carpeta(raiz).glob("*.txt")} if _carpeta(raiz).is_dir() else set()
    n = 1
    while f"clase_{n:04d}" in usados:
        n += 1
    return f"clase_{n:04d}"


def guardar_clase(raiz: Path, texto: str, id_clase: Optional[str] = None, **campos) -> dict:
    """Crea (o reemplaza el texto de) una clase. Sin id, usa el siguiente clase_NNNN."""
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorAccionable("El guion está vacío", "Pega el texto de la clase o sube un archivo .txt")
    id_clase = _validar_id(id_clase) if id_clase else siguiente_id(raiz)
    meta = {**_leer_meta(raiz, id_clase), **_validar_campos(campos)}
    _carpeta(raiz).mkdir(parents=True, exist_ok=True)
    (_carpeta(raiz) / f"{id_clase}.txt").write_text(texto.strip() + "\n", encoding="utf-8")
    _escribir_meta(raiz, id_clase, meta)
    return _ficha(raiz, id_clase)


def importar_guiones(raiz: Path, archivos: List[dict], **campos) -> List[str]:
    """Varios .txt de golpe: el id sale del nombre del archivo; si ya existe se numera (nombre_2). Devuelve los ids."""
    ids = []
    for a in archivos:
        base = re.sub(r"[^A-Za-z0-9_\-]+", "_", Path(str(a.get("nombre", ""))).stem).strip("_")[:50] or siguiente_id(raiz)
        id_clase, n = base, 2
        while (_carpeta(raiz) / f"{id_clase}.txt").is_file():
            id_clase, n = f"{base}_{n}", n + 1
        guardar_clase(raiz, a.get("texto", ""), id_clase, **campos)
        ids.append(id_clase)
    return ids


def actualizar_clase(raiz: Path, id_clase: str, **campos) -> dict:
    _validar_id(id_clase)
    if not (_carpeta(raiz) / f"{id_clase}.txt").is_file():
        raise ErrorAccionable(f"No existe la clase «{id_clase}»", "Actualiza la lista")
    if "texto" in campos:
        texto = campos.pop("texto")
        if not isinstance(texto, str) or not texto.strip():
            raise ErrorAccionable("El guion está vacío", "Escribe el texto de la clase")
        (_carpeta(raiz) / f"{id_clase}.txt").write_text(texto.strip() + "\n", encoding="utf-8")
    _escribir_meta(raiz, id_clase, {**_leer_meta(raiz, id_clase), **_validar_campos(campos)})
    return _ficha(raiz, id_clase)


def leer_texto(raiz: Path, id_clase: str) -> str:
    _validar_id(id_clase)
    ruta = _carpeta(raiz) / f"{id_clase}.txt"
    if not ruta.is_file():
        raise ErrorAccionable(f"No existe la clase «{id_clase}»", "Actualiza la lista")
    return ruta.read_text(encoding="utf-8", errors="replace")


def eliminar_clase(raiz: Path, id_clase: str) -> None:
    """No borra: mueve el guion y sus ajustes a clases/_papelera/ (el audio y el video se quedan donde están)."""
    _validar_id(id_clase)
    papelera = _carpeta(raiz) / "_papelera"
    papelera.mkdir(parents=True, exist_ok=True)
    sello = time.strftime("%Y%m%d-%H%M%S")
    for ext in (".txt", ".json"):
        origen = _carpeta(raiz) / f"{id_clase}{ext}"
        if origen.is_file():
            shutil.move(str(origen), str(papelera / f"{id_clase}-{sello}{ext}"))


# ---------------------------------------------------------------- recursos del proyecto
def escenarios_disponibles(raiz: Path) -> List[dict]:
    carpeta = Path(raiz) / "escenarios"
    if not carpeta.is_dir():
        return []
    salida = []
    for d in sorted(carpeta.iterdir()):
        m = re.match(r"^(E\d+)(?:_(.*))?$", d.name)
        if d.is_dir() and m:
            salida.append({"id": m.group(1), "nombre": m.group(2) or "", "tipo": "video" if (d / "fondo.mp4").is_file() else "imagen"})
    return sorted(salida, key=lambda e: int(e["id"][1:]))


def poses_disponibles(raiz: Path, personaje: str = "profesor") -> List[dict]:
    from src.biblioteca.modelos import _NOMBRE_POSE_V3
    carpeta = Path(raiz) / "personajes" / personaje / "poses"
    if not carpeta.is_dir():
        return []
    salida = []
    for d in sorted(carpeta.iterdir()):
        m = _NOMBRE_POSE_V3.match(d.name)
        if d.is_dir() and m:
            salida.append({"id": d.name, "vista": m.group("vista"), "gesto": m.group("gesto"),
                           "parpadeo": (d / "parpadeo_cerrado.png").is_file()})
    return salida


def _tts_arriba(url: str = "http://127.0.0.1:5055") -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1.5):
            return True
    except Exception:
        return False


def estado_recursos(raiz: Path, personaje: str = "profesor", comprobar_voz: bool = True) -> dict:
    poses = poses_disponibles(raiz, personaje)
    return {"ffmpeg": rutas.FFMPEG.exists(), "rhubarb": rutas.RHUBARB.exists(),
            "tts": _tts_arriba() if comprobar_voz else None,
            "personaje": personaje, "poses": len(poses), "poses_con_parpadeo": sum(p["parpadeo"] for p in poses),
            "vistas": sorted({p["vista"] for p in poses}), "escenarios": escenarios_disponibles(raiz)}


# ---------------------------------------------------------------- voces
def _config_voces(raiz: Path) -> dict:
    from src.tts import _config
    return (_config(Path(raiz)).get("gemini-studio") or {})


def voces_guardadas(raiz: Path) -> Dict[str, Dict[str, Optional[str]]]:
    """{idioma: {hombre: id, mujer: id}} según tts.yaml y tts_usuario.yaml."""
    cfg = _config_voces(raiz)
    es = cfg.get("voces") or {}
    en = ((cfg.get("idiomas") or {}).get("en") or {}).get("voces") or {}
    return {"es": {"hombre": es.get("hombre"), "mujer": es.get("mujer")},
            "en": {"hombre": en.get("hombre"), "mujer": en.get("mujer")}}


def guardar_voces(raiz: Path, idioma: str, hombre: Optional[str], mujer: Optional[str]) -> dict:
    if idioma not in CODIGO_IDIOMA:
        raise ErrorAccionable(f"El idioma «{idioma}» no tiene voces propias", "Elige es o en (mixto usa las de es)")
    ruta = Path(raiz) / "tts_usuario.yaml"
    datos = (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.is_file() else {}
    gem = datos.setdefault("gemini-studio", {})
    voces = {k: v for k, v in (("hombre", hombre), ("mujer", mujer)) if v}
    if not voces:
        raise ErrorAccionable("No elegiste ninguna voz", "Elige al menos una voz antes de guardar")
    if idioma == "es":
        gem.setdefault("voces", {}).update(voces)
        gem["idioma"] = CODIGO_IDIOMA["es"]
    else:
        en = gem.setdefault("idiomas", {}).setdefault("en", {})
        en.setdefault("voces", {}).update(voces)
        en["idioma"] = CODIGO_IDIOMA["en"]
    ruta.write_text("# Voces elegidas en la interfaz (python -m src.ui). Manda sobre tts.yaml; bórralo para volver a lo de tts.yaml.\n"
                    + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return voces_guardadas(raiz)


def listar_voces_remoto(idioma: str, url: str = "http://127.0.0.1:5055") -> List[dict]:
    """Voces del catálogo de gemini-tts-studio para un idioma (id, nombre, género, descripción)."""
    from src.tts.gemini_studio import ProveedorGeminiStudio
    if idioma not in CODIGO_IDIOMA:
        raise ErrorAccionable(f"El idioma «{idioma}» no tiene catálogo de voces", "Elige es o en")
    datos = ProveedorGeminiStudio(url, timeout_s=30)._pedir(f"/api/voices?language={CODIGO_IDIOMA[idioma]}")
    return [{"id": v["id"], "nombre": v.get("name") or v["id"], "genero": (v.get("gender") or "").lower(),
             "descripcion": v.get("description") or ""} for v in datos.get("voces", datos.get("voices", []))]


def muestra_de_voz(raiz: Path, idioma: str, genero: str, voz: Optional[str] = None, texto: Optional[str] = None) -> Path:
    """Genera una frase corta con la voz indicada (o la guardada) para escucharla antes de elegirla."""
    from src.tts import obtener_proveedor
    from src.tts.comun import sintetizar_texto
    idioma_voz = "en" if idioma == "en" else "es"
    proveedor, opciones = obtener_proveedor("gemini-studio", Path(raiz), genero, idioma_voz)
    if voz:
        opciones = dataclasses.replace(opciones, voz=voz)          # OpcionesTTS es inmutable
    destino = Path(raiz) / "cache" / "muestras" / f"{idioma_voz}_{genero}_{re.sub(r'[^A-Za-z0-9_-]+', '_', opciones.voz or 'defecto')}.mp3"
    if not destino.is_file():
        sintetizar_texto(proveedor, texto or TEXTO_MUESTRA[idioma_voz], destino, opciones)
    return destino


# ---------------------------------------------------------------- tareas en segundo plano
def comando_render(raiz: Path, id_clase: str, escenario: str = "", director: bool = True, plano: str = "") -> List[str]:
    """Línea de comandos que renderiza una clase con sus ajustes (la voz debe existir)."""
    ficha = _ficha_de(raiz, id_clase)
    if not ficha["audio"]:
        raise ErrorAccionable(f"La clase «{id_clase}» todavía no tiene voz", "Pulsa «Generar voz» primero")
    cmd = [sys.executable, "-m", "src.render", "--personaje", "profesor", "--audio", str(_carpeta(raiz) / ficha["audio"]),
           "--guion", str(_carpeta(raiz) / f"{id_clase}.txt"), "--idioma", ficha["idioma"]]
    elegido = escenario or next(iter(_lista(ficha["escenarios"])), "")
    if elegido:
        cmd += ["--escenario", elegido]
    poses = _lista(ficha["poses"])
    cmd += ["--poses", ",".join(poses) if poses else "todas"]
    cmd += ["--director" if director else "--no-director"]
    if plano:
        cmd += ["--plano", plano]
    return cmd


def _lista(texto: str) -> List[str]:
    return [x.strip() for x in (texto or "").split(";") if x.strip()]


class Tareas:
    """Registro de trabajos largos (generar voz, renderizar, correr el lote) con su estado y las últimas líneas de log."""

    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self._tareas: Dict[str, dict] = {}
        self._cerrojo = threading.Lock()
        self._n = 0

    def _alta(self, titulo: str, clase: str = "") -> str:
        with self._cerrojo:
            self._n += 1
            tid = f"t{self._n}"
            self._tareas[tid] = {"id": tid, "titulo": titulo, "clase": clase, "estado": "en curso", "inicio": time.time(),
                                 "fin": 0.0, "log": "", "salida": "", "error": ""}
        return tid

    def _cerrar(self, tid: str, ok: bool, salida: str = "", error: str = "") -> None:
        with self._cerrojo:
            t = self._tareas[tid]
            t.update(estado="hecha" if ok else "error", fin=time.time(), salida=salida, error=error)

    def lanzar_funcion(self, titulo: str, fn, clase: str = "") -> str:
        """Ejecuta `fn()` en un hilo; su resultado (ruta) queda como salida y un ErrorAccionable como error legible."""
        tid = self._alta(titulo, clase)

        def correr():
            try:
                self._cerrar(tid, True, str(fn() or ""))
            except ErrorAccionable as exc:
                self._cerrar(tid, False, error=str(exc))
            except Exception as exc:                      # nunca dejar una tarea colgada
                self._cerrar(tid, False, error=f"{type(exc).__name__}: {exc}")
        threading.Thread(target=correr, daemon=True).start()
        return tid

    def lanzar_comando(self, titulo: str, cmd: List[str], clase: str = "", buscar_salida=None) -> str:
        """Ejecuta un comando como proceso aparte y deja su salida (texto) en el log de la tarea."""
        tid = self._alta(titulo, clase)

        def correr():
            try:
                proc = subprocess.Popen(cmd, cwd=str(self.raiz), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        encoding="utf-8", errors="replace", creationflags=SIN_VENTANA,
                                        env={**__import__("os").environ, "PYTHONUTF8": "1"})
                for linea in proc.stdout:
                    with self._cerrojo:
                        self._tareas[tid]["log"] = (self._tareas[tid]["log"] + linea)[-4000:]
                codigo = proc.wait()
                log = self._tareas[tid]["log"]
                if codigo == 0:
                    self._cerrar(tid, True, buscar_salida(log) if buscar_salida else "")
                else:
                    self._cerrar(tid, False, error=_ultimo_error(log) or f"El proceso terminó con código {codigo}")
            except Exception as exc:
                self._cerrar(tid, False, error=f"{type(exc).__name__}: {exc}")
        threading.Thread(target=correr, daemon=True).start()
        return tid

    def listar(self) -> List[dict]:
        with self._cerrojo:
            return [dict(t) for t in sorted(self._tareas.values(), key=lambda t: -t["inicio"])[:30]]


def _ultimo_error(log: str) -> str:
    lineas = [l for l in log.splitlines() if "ERROR" in l or "Error" in l]
    return lineas[-1].strip() if lineas else ""


def salida_de_render(log: str) -> str:
    m = re.search(r"Video listo: (.+)", log)
    return Path(m.group(1).strip()).name if m else ""


# ---------------------------------------------------------------- lote
def crear_lote(raiz: Path, nombre: str, ids: List[str]) -> dict:
    """Escribe el manifiesto de las clases elegidas y las encola (las que ya estaban encoladas se ignoran)."""
    from src.lote.cola import Cola
    from src.lote.manifiesto import encolar_manifiesto, escribir_manifiesto
    if not ids:
        raise ErrorAccionable("No elegiste ninguna clase", "Marca las clases del lote en la lista")
    if not re.match(r"^[\w\-]{1,40}$", nombre or ""):
        raise ErrorAccionable(f"El nombre de lote «{nombre}» no es válido", "Usa letras, números, guion y guion bajo")
    filas = []
    for id_clase in ids:
        f = _ficha_de(raiz, id_clase)
        filas.append({"id": id_clase, "guion": str(_carpeta(raiz) / f"{id_clase}.txt"),
                      "audio": str(_carpeta(raiz) / f["audio"]) if f["audio"] else "", "personaje": "profesor",
                      "escenarios": f["escenarios"], "poses": f["poses"], "resolucion": "1280x720", "semilla": "",
                      "tts": "gemini-studio", "genero": f["genero"], "idioma": f["idioma"], "lote": nombre})
    destino = Path(raiz) / "lote" / "manifiestos" / f"{nombre}.csv"
    escribir_manifiesto(filas, destino)
    nuevos, duplicados = encolar_manifiesto(Cola(Path(raiz) / "lote" / "cola.db"), destino, Path(raiz))
    return {"manifiesto": destino.name, "encoladas": nuevos, "ya_estaban": len(duplicados)}


def estado_lote(raiz: Path) -> dict:
    from src.lote.cola import Cola
    ruta = Path(raiz) / "lote" / "cola.db"
    if not ruta.is_file():
        return {"total": 0, "estados": {}, "trabajos": []}
    cola = Cola(ruta)
    with cola._conexion() as con:
        filas = con.execute("SELECT id, lote, estado, intentos, error, salida, inicio, fin FROM trabajos ORDER BY orden").fetchall()
    trabajos = [{k: f[k] for k in f.keys()} for f in filas]
    estados: Dict[str, int] = {}
    for t in trabajos:
        estados[t["estado"]] = estados.get(t["estado"], 0) + 1
    return {"total": len(trabajos), "estados": estados, "trabajos": trabajos[-200:]}
