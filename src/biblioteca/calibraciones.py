"""Importar poses de la v3 y su calibración de bocas (FR-062, FR-067).

Entradas:
- imágenes de pose con la nomenclatura <vista>_<gesto>_<NN>.png (PNG con transparencia);
- el JSON que exportan los calibradores (una sola pose, o «Copiar TODAS las poses»);
- una carpeta de bocas por vista (nueve PNG A–H y X, con cualquier prefijo: boca34_A.png, boca_A.png, A.png).

Resultado en personajes/<personaje>/poses/<id>/: cuerpo.png y config.yaml (v4). El juego de bocas de
cada vista se guarda UNA vez, en una pose «dueña» (la neutro_01 de la vista, o la primera), y las demás
poses de la vista lo comparten con `bocas_de`."""
import filecmp
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from PIL import Image, UnidentifiedImageError

from src.alineacion import centro_cabeza
from src.biblioteca.config_pose import escribir_config_pose_v4
from src.biblioteca.importador import IMAGENES, InformeImportacion, Rechazo
from src.biblioteca.modelos import _NOMBRE_POSE_V3
from src.biblioteca.validacion import VISEMAS
from src.errores import AssetInvalido

SUFIJOS_PARPADEO = ("_parpadeo", "_parpadeo_medio")
EJEMPLO = "frontal_neutro_01.png o tres_cuartos_der_explicar_01.png"


def leer_calibraciones(ruta: Path) -> Dict[str, dict]:
    """Devuelve {pose: {"espejo": bool, "formas": {A..X: {x, y, s, r, m}}}} a partir del JSON de los
    calibradores. Valida que cada pose traiga las nueve formas. La clave es la que trae el archivo
    (los calibradores usan nombres cortos como «explicar_01»)."""
    return leer_calibraciones_con_juego(ruta)[0]


def leer_calibraciones_con_juego(ruta: Path):
    """Como `leer_calibraciones`, pero también devuelve el «juego» del archivo (p. ej. tres_cuartos)."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise AssetInvalido(f"No existe el archivo de calibración {ruta}",
                            "Pulsa «Copiar TODAS las poses» en el calibrador y guarda el JSON en un archivo")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise AssetInvalido(f"{ruta.name} no es un JSON válido ({exc})",
                            "Vuelve a copiarlo desde el calibrador y guárdalo sin editar") from exc
    if isinstance(datos, dict) and isinstance(datos.get("poses"), dict):
        crudas = datos["poses"]
    elif isinstance(datos, dict) and datos.get("pose") and isinstance(datos.get("formas"), dict):
        crudas = {datos["pose"]: {"espejo": datos.get("espejo", False), "formas": datos["formas"]}}
    else:
        crudas = {}
    if not crudas:
        raise AssetInvalido(f"{ruta.name} no contiene ninguna pose calibrada",
                            "Usa el JSON de «Copiar» (una pose) o «Copiar TODAS las poses» del calibrador")
    resultado: Dict[str, dict] = {}
    for pose_id, c in crudas.items():
        formas = (c or {}).get("formas") or {}
        faltan = [v for v in VISEMAS if v not in formas]
        if faltan:
            raise AssetInvalido(f"Faltan formas en la calibración de {pose_id}: {', '.join(faltan)}",
                                "Calibra las 9 formas (A–H y X) antes de exportar")
        resultado[pose_id] = {"espejo": bool(c.get("espejo", False)), "formas": formas}
    return resultado, (datos.get("juego") if isinstance(datos, dict) else None)


def _resolver_claves(cal: Dict[str, dict], ids: List[str], juego: Optional[str], avisos: List[str]) -> Dict[str, dict]:
    """Lleva las claves de la calibración a ids completos de pose. Una clave corta («explicar_01») se asigna
    a la pose de la vista que corresponda al `juego` del archivo; si hay varias posibles y no se puede
    decidir, no se adivina: se avisa."""
    resueltas: Dict[str, dict] = {}
    for clave, datos in cal.items():
        if clave in ids:
            resueltas[clave] = datos
            continue
        candidatas = [i for i in ids if i.endswith("_" + clave)]
        if len(candidatas) > 1 and juego:
            candidatas = [i for i in candidatas if i.startswith(juego)] or candidatas
        if len(candidatas) == 1:
            resueltas[candidatas[0]] = datos
        elif len(candidatas) > 1:
            avisos.append(f"{clave}: el nombre es ambiguo ({', '.join(sorted(candidatas))}) y el archivo no indica "
                          "el juego; renombra la pose en el calibrador con el id completo o importa cada vista por separado")
        else:
            resueltas[clave] = datos            # sin imagen: se avisará más adelante como «sin imagen»
    return resueltas


def _calibracion_existente(carpeta: Path) -> Optional[dict]:
    """La calibración que la pose ya tiene en el proyecto (o None si nunca se calibró)."""
    from src.biblioteca.modelos import cargar_pose
    if not (carpeta / "config.yaml").is_file():
        return None
    try:
        pose = cargar_pose(carpeta)
    except AssetInvalido:
        return None
    if not pose.formas:
        return None
    return {"espejo": bool(pose.espejo),
            "formas": {v: {"x": f.x, "y": f.y, "s": f.s, "r": f.r, "m": f.m} for v, f in pose.formas.items()}}


def _sprites_de_vista(carpeta: Path) -> Dict[str, Path]:
    encontrados: Dict[str, Path] = {}
    for v in VISEMAS:
        patron = re.compile(rf"^(?:.*[_\- ])?{v}\.png$", re.IGNORECASE)
        candidatos = sorted(p for p in carpeta.iterdir() if p.is_file() and patron.match(p.name))
        if candidatos:
            encontrados[v] = candidatos[0]
    return encontrados


def _dueña_de_la_vista(ids: List[str]) -> str:
    """Pose que guarda las bocas de la vista: la neutro_01 y, a falta de ella, la primera por gesto."""
    def clave(i: str):
        m = _NOMBRE_POSE_V3.match(i)
        return (m.group("gesto") != "neutro", m.group("gesto"), int(m.group("nn")))
    return sorted(ids, key=clave)[0]


def importar_poses(origen: Union[Path, Sequence[Path]], raiz: Path, personaje: str = "profesor",
                   calibraciones: Optional[Path] = None,
                   bocas: Optional[Dict[str, Path]] = None) -> InformeImportacion:
    raiz = Path(raiz)
    origenes = [Path(origen)] if isinstance(origen, (str, Path)) else [Path(o) for o in origen]
    poses_dir = raiz / "personajes" / personaje / "poses"
    informe = InformeImportacion()
    cal, juego = leer_calibraciones_con_juego(calibraciones) if calibraciones else ({}, None)

    # 1) reunir las imágenes de pose
    imagenes: Dict[str, Path] = {}
    for carpeta in origenes:
        if not carpeta.is_dir():
            raise AssetInvalido(f"No existe la carpeta de poses {carpeta}", "Revisa la ruta indicada en --origen")
        for archivo in sorted(carpeta.iterdir()):
            if not archivo.is_file() or archivo.suffix.lower() not in IMAGENES:
                continue
            if archivo.stem.endswith(SUFIJOS_PARPADEO):
                informe.avisos.append(f"{archivo.name}: es una imagen de parpadeo; se importa con la tarea de parpadeo (T100)")
                continue
            if not _NOMBRE_POSE_V3.match(archivo.stem) or " " in archivo.stem:
                informe.rechazados.append(Rechazo(archivo.name,
                                                  f"el nombre no sigue la nomenclatura <vista>_<gesto>_<NN> (por ejemplo {EJEMPLO})"))
                continue
            try:
                with Image.open(archivo) as im:
                    modo = im.mode
                    alfa_min = im.getchannel("A").getextrema()[0] if modo == "RGBA" else 255
            except (UnidentifiedImageError, OSError):
                informe.rechazados.append(Rechazo(archivo.name, "no se pudo leer como imagen; reexpórtala como PNG"))
                continue
            if modo != "RGBA" or alfa_min == 255:
                informe.rechazados.append(Rechazo(
                    archivo.name, "debe ser PNG con transparencia (fondo transparente) y esta imagen no la tiene; "
                                  "recorta al personaje o ejecuta la segmentación"))
                continue
            imagenes[archivo.stem] = archivo

    # 2) claves cortas de los calibradores -> ids completos, y poses que solo traen calibración pero
    #    ya existen en disco (se actualiza su config)
    existentes = [d.name for d in poses_dir.iterdir() if d.is_dir()] if poses_dir.is_dir() else []
    cal = _resolver_claves(cal, sorted(set(imagenes) | set(existentes)), juego, informe.avisos)
    for pose_id in list(cal):
        if pose_id not in imagenes:
            existente = poses_dir / pose_id / "cuerpo.png"
            if existente.is_file():
                imagenes[pose_id] = existente
            else:
                informe.avisos.append(f"{pose_id}: hay calibración pero no hay imagen de esa pose; se ignora")

    # 3) bocas por vista: se copian UNA vez a la pose dueña
    por_vista: Dict[str, List[str]] = {}
    for pose_id in imagenes:
        por_vista.setdefault(_NOMBRE_POSE_V3.match(pose_id).group("vista"), []).append(pose_id)
    dueñas: Dict[str, str] = {}
    for vista, ids in por_vista.items():
        existentes = [d.name for d in poses_dir.iterdir() if d.is_dir() and d.name.startswith(vista + "_")
                      and (d / "bocas").is_dir()] if poses_dir.is_dir() else []
        dueña = existentes[0] if existentes else _dueña_de_la_vista(ids)
        dueñas[vista] = dueña
        carpeta_bocas = (bocas or {}).get(vista)
        if carpeta_bocas is None:
            continue
        sprites = _sprites_de_vista(Path(carpeta_bocas)) if Path(carpeta_bocas).is_dir() else {}
        faltan = [v for v in VISEMAS if v not in sprites]
        if faltan:
            informe.rechazados.append(Rechazo(
                str(carpeta_bocas), f"faltan bocas de la vista {vista}: {', '.join(faltan)} "
                                    "(se necesitan A, B, C, D, E, F, G, H y X en PNG con transparencia)"))
            continue
        destino = poses_dir / dueña / "bocas"
        destino.mkdir(parents=True, exist_ok=True)
        for v, ruta in sprites.items():
            shutil.copyfile(ruta, destino / f"{v}.png")
        informe.importados.append(f"bocas de la vista {vista} -> {destino.relative_to(raiz)}")

    # 4) cada pose: cuerpo.png + config.yaml
    for pose_id, ruta in sorted(imagenes.items()):
        m = _NOMBRE_POSE_V3.match(pose_id)
        carpeta = poses_dir / pose_id
        carpeta.mkdir(parents=True, exist_ok=True)
        cuerpo = carpeta / "cuerpo.png"
        if ruta.resolve() != cuerpo.resolve() and not (cuerpo.is_file() and filecmp.cmp(ruta, cuerpo, shallow=False)):
            shutil.copyfile(ruta, cuerpo)
        with Image.open(cuerpo) as im:
            lienzo, pelo = im.size, centro_cabeza(im)
        c = cal.get(pose_id) or _calibracion_existente(carpeta)       # sin archivo nuevo, no se borra lo ya calibrado
        if c is None:
            informe.avisos.append(f"{pose_id}: sin calibración de bocas; calíbrala con el calibrador "
                                  "(Calibrador4) y vuelve a importar")
        dueña = dueñas[m.group("vista")]
        escribir_config_pose_v4(carpeta, m.group("vista"), m.group("gesto"), int(m.group("nn")), lienzo,
                                (c or {}).get("formas", {}), espejo=bool((c or {}).get("espejo", False)),
                                bocas_de=None if pose_id == dueña else dueña, pelo=pelo)
        informe.importados.append(f"{pose_id} -> {carpeta.relative_to(raiz)}")
    return informe
