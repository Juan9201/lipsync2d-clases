"""Lógica de la interfaz web local (FR-064, FR-071): guiones, voces, render y lote. Sin HTTP aquí: el servidor solo
traduce peticiones a estas funciones, así se prueban sin navegador.

Los guiones viven en `clases/<id>.txt` con sus ajustes (idioma, voz, escenarios y poses permitidos) en `clases/<id>.json`.
La voz es siempre la misma (podcaster-3); solo se elige entre el acento colombiano y el neutro (perfiles de tts.yaml)."""
import io
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src import rutas
from src.audio import SIN_VENTANA
from src.errores import ErrorAccionable

ID_VALIDO = re.compile(r"^[A-Za-z0-9_\-]{1,60}$")
IDIOMAS = ("es", "en", "mixto")
GENEROS = ("hombre", "mujer")
CAMPOS_CLASE = ("idioma", "voz", "escenarios", "poses")
VOCES = ("colombiano", "neutro")                                   # el casting: la misma voz con o sin acento colombiano


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
    return {"idioma": datos.get("idioma", "es"), "genero": "hombre", "voz": datos.get("voz", "colombiano"),
            "escenarios": datos.get("escenarios", ""), "poses": datos.get("poses", "")}


def _escribir_meta(raiz: Path, id_clase: str, meta: dict) -> None:
    (_carpeta(raiz) / f"{id_clase}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def _validar_campos(campos: dict) -> dict:
    limpio = {}
    if "idioma" in campos:
        if campos["idioma"] not in IDIOMAS:
            raise ErrorAccionable(f"El idioma «{campos['idioma']}» no es válido", f"Usa {', '.join(IDIOMAS)}")
        limpio["idioma"] = campos["idioma"]
    if "voz" in campos:
        if campos["voz"] not in VOCES:
            raise ErrorAccionable(f"La voz «{campos['voz']}» no es válida", f"Usa {' o '.join(VOCES)}")
        limpio["voz"] = campos["voz"]
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
CARPETA_ESCENARIO = re.compile(r"^(E\d+)(?:_(.*))?$")
EXTENSIONES_FONDO = (".png", ".jpg", ".jpeg", ".webp", ".mp4")
MIN_FONDO = (1280, 720)


def _fondo_de(carpeta: Path) -> Optional[Path]:
    return next((carpeta / n for n in ("fondo.mp4", "fondo.png", "fondo.jpg") if (carpeta / n).is_file()), None)


def _medidas(fondo: Path) -> dict:
    """Tipo, medidas (y duración si es video) de un fondo; vacío si no se puede leer."""
    try:
        if fondo.suffix.lower() == ".mp4":
            from src.layers.fondo_video import _sondear
            i = _sondear(fondo)
            return {"tipo": "video", "ancho": i["ancho"], "alto": i["alto"], "duracion": round(i["duracion"], 1)}
        from PIL import Image
        with Image.open(fondo) as im:
            return {"tipo": "imagen", "ancho": im.width, "alto": im.height, "duracion": None}
    except Exception:
        return {"tipo": "video" if fondo.suffix.lower() == ".mp4" else "imagen", "ancho": 0, "alto": 0, "duracion": None}


def escenarios_disponibles(raiz: Path) -> List[dict]:
    carpeta = Path(raiz) / "escenarios"
    if not carpeta.is_dir():
        return []
    salida = []
    for d in sorted(carpeta.iterdir()):
        m = CARPETA_ESCENARIO.match(d.name)
        if d.is_dir() and m:
            fondo = _fondo_de(d)
            from src.escena.config import es_escena
            from src.escena.config import fraccion_transparente
            salida.append({"id": m.group(1), "nombre": m.group(2) or "", "carpeta": d.name, "capas": es_escena(d),
                           "transparente": fraccion_transparente(fondo) if fondo else 0.0,
                           **(_medidas(fondo) if fondo else {"tipo": "imagen", "ancho": 0, "alto": 0, "duracion": None})})
    return sorted(salida, key=lambda e: int(e["id"][1:]))


def _nombre_seguro(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    base = Path(base.replace("\\", "/")).name                      # nunca una ruta
    return re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")[:30] or "fondo"


def agregar_escenario(raiz: Path, nombre: str, extension: str, origen: Path, reemplazar: Optional[str] = None) -> dict:
    """Valida un fondo (imagen 16:9 o MP4 de al menos 1 s) y lo deja en escenarios/E<n>_<nombre>/fondo.<ext>. Un número nuevo
    es el siguiente al mayor; con `reemplazar` ("E2") conserva su número y el fondo anterior va a escenarios/_papelera."""
    from src.biblioteca.validacion import validar_escenario
    from src.layers.fondo_video import DURACION_MINIMA_S
    raiz, origen = Path(raiz), Path(origen)
    ext = (extension or "").lower()
    if ext not in EXTENSIONES_FONDO:
        raise ErrorAccionable(f"El archivo «{ext or 'sin extensión'}» no se puede usar como fondo",
                              "Sube una imagen PNG o JPG (también WebP) o un video MP4")
    base = raiz / "escenarios"
    existentes = escenarios_disponibles(raiz)
    if reemplazar:
        destino_info = next((e for e in existentes if e["id"] == reemplazar), None)
        if destino_info is None:
            raise ErrorAccionable(f"No existe el escenario «{reemplazar}» para reemplazar", "Actualiza la lista de escenarios")
        carpeta, numero = base / destino_info["carpeta"], reemplazar
    else:
        numero = f"E{max((int(e['id'][1:]) for e in existentes), default=0) + 1}"
        carpeta = base / f"{numero}_{_nombre_seguro(nombre)}"
    # 1) se prepara y valida aparte: si algo falla no se toca lo que ya había
    prueba = raiz / "cache" / "subidas" / f"validar_{numero}_{int(time.time() * 1000)}"
    prueba.mkdir(parents=True)
    try:
        if ext == ".webp":
            from PIL import Image
            try:
                with Image.open(origen) as im:
                    im.convert("RGB").save(prueba / "fondo.png")
            except Exception as exc:
                raise ErrorAccionable("No se pudo leer la imagen WebP", "Expórtala de nuevo como PNG o JPG") from exc
            nombre_fondo = "fondo.png"
        else:
            nombre_fondo = "fondo" + (".jpg" if ext == ".jpeg" else ext)
            shutil.copyfile(origen, prueba / nombre_fondo)
        validar_escenario(prueba)                                   # 16:9 y legible (AssetInvalido es un ErrorAccionable)
        medidas = _medidas(prueba / nombre_fondo)
        if medidas["tipo"] == "video" and (medidas["duracion"] or 0) < DURACION_MINIMA_S:
            raise ErrorAccionable(f"El video dura solo {medidas['duracion']} segundos",
                                  f"Usa un video de al menos {DURACION_MINIMA_S:.0f} segundo (lo ideal son 10 a 20)")
        # 2) se coloca: el fondo anterior (si se reemplaza) pasa a la papelera
        if carpeta.is_dir():
            papelera = base / "_papelera" / f"{carpeta.name}-{time.strftime('%Y%m%d-%H%M%S')}"
            papelera.mkdir(parents=True)
            for viejo in carpeta.glob("fondo.*"):
                shutil.move(str(viejo), str(papelera / viejo.name))
        carpeta.mkdir(parents=True, exist_ok=True)
        shutil.move(str(prueba / nombre_fondo), str(carpeta / nombre_fondo))
    finally:
        shutil.rmtree(prueba, ignore_errors=True)
        try:
            (raiz / "cache" / "subidas").rmdir()
        except OSError:
            pass
    aviso = ""
    if medidas["ancho"] < MIN_FONDO[0] or medidas["alto"] < MIN_FONDO[1]:
        aviso = f"Mide {medidas['ancho']}x{medidas['alto']}, menos de {MIN_FONDO[0]}x{MIN_FONDO[1]}: se verá ampliado y borroso"
    return {"id": numero, "carpeta": carpeta.name, "nombre": carpeta.name.split("_", 1)[1] if "_" in carpeta.name else "",
            **medidas, "aviso": aviso}


# ---------------------------------------------------------------- escenas con capas
PLANOS_EDITOR = ("PL1", "PL2", "PL3", "PL4", "PL5")
_poses_cache: Dict[str, object] = {}
_vistas_cache: Dict[str, object] = {}
_cerrojo_vista = threading.Lock()


def subir_frente(raiz: Path, carpeta: str, origen: Path) -> dict:
    """Guarda la capa delantera (frente.png): PNG con transparencia, del mismo tamaño que el fondo. Si la escena aún no tenía
    configuración, se crea con luces detectadas."""
    from PIL import Image
    from src.escena import config as cfgmod
    ruta = _carpeta_escenario(raiz, carpeta)
    fondo = _fondo_de(ruta)
    if fondo is None:
        raise ErrorAccionable(f"El escenario {carpeta} no tiene fondo", "Sube primero el fondo trasero")
    try:
        with Image.open(origen) as im:
            tam, modo = im.size, im.mode
            alfa_min = im.convert("RGBA").getchannel("A").getextrema()[0]
            rgba = im.convert("RGBA")
    except Exception as exc:
        raise ErrorAccionable("No se pudo leer la capa delantera como imagen", "Expórtala como PNG con transparencia") from exc
    if alfa_min == 255:
        raise ErrorAccionable("La capa delantera no tiene transparencia", "Debe ser un PNG con fondo transparente: solo la mesa y lo que va delante del personaje")
    ancho, alto = cfgmod.lienzo_de(ruta)
    if tam != (ancho, alto):
        raise ErrorAccionable(f"La capa delantera mide {tam[0]}x{tam[1]} y el fondo {ancho}x{alto}",
                              "Las dos capas deben tener exactamente el mismo tamaño y estar alineadas")
    destino = ruta / "frente.png"
    temporal = ruta / "frente.png.tmp"
    rgba.save(temporal, "PNG")
    temporal.replace(destino)
    cfg = cfgmod.guardar_config(ruta, cfgmod.cargar_config(ruta)) if not (ruta / cfgmod.ARCHIVO).is_file() else cfgmod.cargar_config(ruta)
    return {"carpeta": carpeta, "capas": True, "luces_detectadas": len(cfg["luz"]["luces"])}


def _poses_v3(raiz: Path, personaje: str = "profesor") -> Dict[str, object]:
    """Todas las poses por vista del personaje, cargadas una vez (la neutra frontal primero: es la referencia de la cabeza)."""
    from src.biblioteca.modelos import cargar_pose
    base = Path(raiz) / "personajes" / personaje / "poses"
    ids = [p["id"] for p in poses_disponibles(raiz, personaje)]
    if not ids:
        raise ErrorAccionable(f"El personaje «{personaje}» no tiene poses por vista", "Impórtalas con `python -m src.biblioteca importar-poses`")
    ids.sort(key=lambda i: (i != "frontal_neutro_01", not i.endswith("_neutro_01"), i))
    clave = f"{base}|{len(ids)}"
    if clave not in _poses_cache:
        _poses_cache.clear()
        _poses_cache[clave] = {i: cargar_pose(base / i) for i in ids}
    return _poses_cache[clave]


def config_escena(raiz: Path, carpeta: str) -> dict:
    """La configuración de la escena y lo que el editor necesita para ofrecerla (poses y planos)."""
    from src.escena import config as cfgmod
    ruta = _carpeta_escenario(raiz, carpeta)
    if not cfgmod.es_escena(ruta):
        raise ErrorAccionable(f"El escenario {carpeta} no tiene capas", "Sube la capa delantera (frente) para poder editarlo como escena")
    return {"config": cfgmod.cargar_config(ruta), "poses": poses_disponibles(raiz), "planos": list(PLANOS_EDITOR)}


def guardar_escena(raiz: Path, carpeta: str, config: dict) -> dict:
    from src.escena import config as cfgmod
    ruta = _carpeta_escenario(raiz, carpeta)
    if not isinstance(config, dict) or not all(k in config for k in ("personaje", "mesa", "luz")):
        raise ErrorAccionable("La configuración de la escena está incompleta", "Recarga el editor e inténtalo de nuevo")
    return cfgmod.guardar_config(ruta, config)


def vista_escena(raiz: Path, carpeta: str, config: dict, pose: str, plano: str, visema: str = "X", ojos: str = "abierto",
                 luz: bool = True, borrador: bool = False):
    """Un cuadro de la escena con la configuración que se está editando (sin guardarla): (JPEG, ventana del plano en la escena)."""
    from src.escena import config as cfgmod
    from src.escena.escena import EscenaLayer, activos_de
    ruta = _carpeta_escenario(raiz, carpeta)
    if plano not in PLANOS_EDITOR:
        raise ErrorAccionable(f"El plano «{plano}» no es válido", f"Usa {', '.join(PLANOS_EDITOR)}")
    if visema not in "ABCDEFGHX" or len(visema) != 1:
        raise ErrorAccionable(f"La forma de boca «{visema}» no es válida", "Usa A–H o X")
    if ojos not in ("abierto", "medio", "cerrado"):
        raise ErrorAccionable(f"El estado de ojos «{ojos}» no es válido", "Usa abierto, medio o cerrado")
    poses = _poses_v3(raiz)
    if pose not in poses:
        raise ErrorAccionable(f"La pose «{pose}» no existe", "Las poses disponibles son: " + ", ".join(poses))
    lienzo = cfgmod.lienzo_de(ruta)
    base = cfgmod.config_defecto(lienzo)
    cfgmod._fusionar(base, json.loads(json.dumps(config)))
    limpia = cfgmod.validar_config(base, lienzo)
    salida = (640, 360) if borrador else (960, 540)
    clave = json.dumps([str(ruta), limpia, salida], sort_keys=True)
    with _cerrojo_vista:
        capa = _vistas_cache.get(clave)
        if capa is None:
            _vistas_cache.clear()                                    # una sola configuración a la vez: el editor la cambia sin parar
            capa = _vistas_cache[clave] = EscenaLayer(ruta, limpia, poses, salida, alinear=True, activos=activos_de(ruta))
        imagen = capa.vista(pose, plano, visema, ojos, luz)
        v = capa.ventana_escena(plano)
    buf = io.BytesIO()
    imagen.save(buf, "JPEG", quality=82 if borrador else 90)
    return buf.getvalue(), (v.x0, v.y0, v.w, v.h)


def _carpeta_escenario(raiz: Path, carpeta: str) -> Path:
    if not CARPETA_ESCENARIO.match(carpeta or "") or "/" in carpeta or "\\" in carpeta:
        raise ErrorAccionable(f"El escenario «{carpeta}» no es válido", "Actualiza la lista de escenarios")
    ruta = Path(raiz) / "escenarios" / carpeta
    if not ruta.is_dir():
        raise ErrorAccionable(f"No existe el escenario «{carpeta}»", "Actualiza la lista de escenarios")
    return ruta


def quitar_escenario(raiz: Path, carpeta: str) -> None:
    """No borra: mueve el escenario entero a escenarios/_papelera/."""
    ruta = _carpeta_escenario(raiz, carpeta)
    destino = Path(raiz) / "escenarios" / "_papelera"
    destino.mkdir(exist_ok=True)
    shutil.move(str(ruta), str(destino / f"{carpeta}-{time.strftime('%Y%m%d-%H%M%S')}"))


def miniatura_escenario(raiz: Path, carpeta: str) -> Path:
    """JPG de 480 px de ancho del fondo (en un video, el fotograma de 1 s); se rehace si el fondo cambió."""
    ruta = _carpeta_escenario(raiz, carpeta)
    fondo = _fondo_de(ruta)
    if fondo is None:
        raise ErrorAccionable(f"El escenario {carpeta} no tiene fondo", "Súbele un fondo")
    destino = Path(raiz) / "cache" / "miniaturas" / f"{carpeta}.jpg"
    if destino.is_file() and destino.stat().st_mtime >= fondo.stat().st_mtime:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    if fondo.suffix.lower() == ".mp4":
        subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-ss", "1", "-i", str(fondo), "-frames:v", "1", "-vf", "scale=480:-2", str(destino)],
                       check=True, creationflags=SIN_VENTANA)
        if not destino.is_file():                                        # video más corto de 1 s: primer fotograma
            subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-i", str(fondo), "-frames:v", "1", "-vf", "scale=480:-2", str(destino)],
                           check=True, creationflags=SIN_VENTANA)
    else:
        from PIL import Image
        with Image.open(fondo) as im:
            im = im.convert("RGB")
            im.thumbnail((480, 480))
            im.save(destino, quality=82)
    return destino


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
                      "tts": "gemini-studio", "genero": "hombre", "idioma": f["idioma"], "voz": f["voz"], "lote": nombre})
    destino = Path(raiz) / "lote" / "manifiestos" / f"{nombre}.csv"
    escribir_manifiesto(filas, destino)
    nuevos, duplicados = encolar_manifiesto(Cola(Path(raiz) / "lote" / "cola.db"), destino, Path(raiz))
    return {"manifiesto": destino.name, "encoladas": nuevos, "ya_estaban": len(duplicados)}


def progreso_en_vivo(raiz: Path) -> dict:
    """Etapas y cuadros de las clases que se están procesando (y las últimas terminadas), con la hora del servidor en ms."""
    from src.progreso import leer_todos
    ahora = int(time.time() * 1000)
    return {"ahora_ms": ahora, "clases": leer_todos(raiz, ahora_ms=ahora), "cola": resumen_cola(raiz)}


def resumen_cola(raiz: Path) -> dict:
    """Avance global de la cola: renderizadas, publicadas (con subtítulos, ya en Drive) y por cumplir."""
    import sqlite3
    def contar(ruta: Path, tabla: str) -> Dict[str, int]:
        if not ruta.is_file():
            return {}
        con = sqlite3.connect(str(ruta))
        try:
            return dict(con.execute(f"SELECT estado, COUNT(*) FROM {tabla} GROUP BY estado").fetchall())
        except sqlite3.Error:
            return {}
        finally:
            con.close()
    c = contar(Path(raiz) / "lote" / "cola.db", "trabajos")
    p = contar(Path(raiz) / "lote" / "publicacion.db", "pub")
    total = sum(c.values())
    hechas = c.get("hecho", 0)
    return {"total": total, "renderizadas": hechas, "en_proceso": c.get("en_proceso", 0), "con_error": c.get("error", 0),
            "publicadas": p.get("publicado", 0), "por_cumplir": total - hechas}


def _abrir_en_explorador(carpeta: Path) -> None:
    import os
    if hasattr(os, "startfile"):
        os.startfile(str(carpeta))                                       # Windows: abre el Explorador de archivos
    else:
        subprocess.Popen(["xdg-open", str(carpeta)])


def abrir_carpeta_salidas(raiz: Path) -> dict:
    """Abre la carpeta donde quedan los videos (`salidas/`) en el explorador de archivos del equipo."""
    carpeta = Path(raiz) / "salidas"
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        _abrir_en_explorador(carpeta)
    except OSError as exc:
        raise ErrorAccionable(f"No se pudo abrir la carpeta de videos: {exc}", f"Ábrela a mano: {carpeta}") from exc
    return {"carpeta": str(carpeta)}


def preparar_produccion(raiz: Path, ids: List[str], escenario: str = "") -> dict:
    """«Producir marcadas»: comprueba todo antes de tocar nada, asigna el escenario a las clases elegidas (vacío = automático, no se
    cambia nada) y las encola en un lote con nombre automático. Arrancar los trabajadores lo hace el servidor."""
    if not ids:
        raise ErrorAccionable("No marcaste ninguna clase", "Marca en la lista las clases que quieres producir")
    ids = list(dict.fromkeys(ids))
    for id_clase in ids:
        _ficha_de(raiz, id_clase)
    if escenario and escenario not in {e["id"] for e in escenarios_disponibles(raiz)}:
        raise ErrorAccionable(f"El escenario «{escenario}» no existe", "Elige uno de la lista de escenarios")
    if escenario:
        for id_clase in ids:
            if _leer_meta(raiz, id_clase)["escenarios"] != escenario:
                actualizar_clase(raiz, id_clase, escenarios=escenario)
    nombre = "prod-" + time.strftime("%Y%m%d-%H%M%S")
    return {"lote": nombre, **crear_lote(raiz, nombre, ids)}


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
