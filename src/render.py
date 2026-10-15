"""Orquestador de un trabajo de render (FR-070, NFR-006): de la clase (audio + guion) al MP4.

Uso:  python -m src.render --personaje profesor --audio clases\\clase_0001.mp3 [--guion ...]
"""
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Sequence, Tuple

from src import rutas
from src.audio import convertir_para_analisis, info_audio
from src.biblioteca.validacion import validar_escenario, validar_pose
from src.animation import calcular_hablando, generar_animacion, generar_parpadeos
from src.compositor import Compositor
from src.encoder import Codificador
from src.errores import AssetInvalido
from src.guion import limpiar_para_analisis
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.concretas import AnclasEstaticas, BocaLayer, CuerpoLayer, FondoLayer, OjosLayer
from src.layers.fondo_video import FondoVideoLayer
from src.layers.personaje import PersonajeLayer
from src.lipsync import analizar, cues_a_frames, suavizar
from src.registro import etapa, obtener_logger
from src.timeline import LineaDeTiempo, Toma, Visema, semilla_de_clase, tomas_ciclicas

FPS = 25


@dataclass
class ParametrosRender:
    personaje: str
    audio: Path
    guion: Optional[Path] = None
    pose: Optional[str] = None
    escenario: Optional[str] = None
    resolucion: Tuple[int, int] = (1280, 720)
    semilla: int = 0
    reconocedor: str = "phonetic"
    plano: str = "PL1"
    clase_id: Optional[str] = None     # identificador de la clase (por defecto, el nombre del audio)
    # --- v3: varias poses con la cabeza alineada ---
    poses: Optional[Sequence[str]] = None   # ids de pose (<vista>_<gesto>_<NN>); se recorren en ciclo
    alinear: bool = True               # FR-059: llevar la cabeza de cada pose al sitio de la primera
    duracion_toma_s: float = 25.0      # cada cuánto cambia de pose (provisional hasta el director)


def _buscar_carpeta(base: Path, prefijo: str, id_pedido: Optional[str]) -> Optional[Path]:
    if not base.is_dir():
        return None
    if id_pedido and (base / id_pedido).is_dir():          # id exacto, p. ej. frontal_neutro_01 (v3)
        return base / id_pedido
    candidatas = sorted(d for d in base.iterdir() if d.is_dir() and re.match(rf"^{prefijo}\d+(_|$)", d.name))
    if id_pedido:
        return next((d for d in candidatas if re.match(rf"^{re.escape(id_pedido)}(_|$)", d.name)), None)
    return candidatas[0] if candidatas else None


def _cargar_poses_de_la_clase(poses_dir: Path, ids: Sequence[str]) -> dict:
    """Valida y carga las poses pedidas (v3); una inexistente lista las disponibles (NFR-006)."""
    disponibles = sorted(d.name for d in poses_dir.iterdir() if d.is_dir()) if poses_dir.is_dir() else []
    cargadas = {}
    for pose_id in ids:
        if pose_id not in disponibles:
            raise AssetInvalido(f"La pose «{pose_id}» no existe en {poses_dir}",
                                "Las poses disponibles son: " + (", ".join(disponibles) or "(ninguna)"))
        cargadas[pose_id] = validar_pose(poses_dir / pose_id)
    return cargadas


def _a_visemas(frames) -> list:
    visemas, ini = [], 0
    for i in range(1, len(frames) + 1):
        if i == len(frames) or frames[i] != frames[ini]:
            visemas.append(Visema(ini, i, frames[ini]))
            ini = i
    return visemas


def renderizar(p: ParametrosRender, raiz: Path = rutas.RAIZ) -> Path:
    raiz = Path(raiz)
    clase_id = p.clase_id or Path(p.audio).stem
    log = obtener_logger("render", archivo=raiz / "logs" / f"{clase_id}.log")
    W, H = p.resolucion

    audio = Path(p.audio)
    if not audio.is_file():
        raise AssetInvalido(f"El archivo de audio no existe: {audio}", "Revisa la ruta indicada en --audio")

    with etapa(log, "assets"):
        poses_dir = raiz / "personajes" / p.personaje / "poses"
        poses_clase = {}
        if p.poses:
            poses_clase = _cargar_poses_de_la_clase(poses_dir, list(p.poses))
            pose = next(iter(poses_clase.values()))         # la primera es la de referencia (cabeza y encuadre)
        else:
            carpeta_pose = _buscar_carpeta(poses_dir, "P", p.pose)
            if carpeta_pose is None:
                raise AssetInvalido(
                    f"El personaje «{p.personaje}» no tiene poses" + (f" ({p.pose})" if p.pose else ""),
                    "Suelta las imágenes en entrada/ y ejecuta `python -m src.biblioteca importar` "
                    "(o `importar-poses` para las poses por vista)")
            pose = validar_pose(carpeta_pose)
            poses_clase = {pose.id: pose}
        ruta_fondo = None
        if not pose.respaldo:
            carpeta_esc = _buscar_carpeta(raiz / "escenarios", "E", p.escenario)
            if carpeta_esc is None:
                raise AssetInvalido("No hay ningún escenario disponible para esta pose",
                                    "Sube un escenario (por ejemplo E1_salon.png) a entrada/ y ejecuta "
                                    "`python -m src.biblioteca importar`")
            ruta_fondo = validar_escenario(carpeta_esc, (W, H))
        info = info_audio(audio)

    texto = ""
    if p.guion is not None and Path(p.guion).is_file():
        texto = limpiar_para_analisis(Path(p.guion).read_text(encoding="utf-8"))
    if not texto:
        log.info("Clase sin guion: se usa una sola toma y el lipsync no recibe texto de apoyo")

    with etapa(log, "rhubarb"):
        wav = raiz / "cache" / "analisis" / f"{clase_id}.wav"
        try:
            convertir_para_analisis(audio, wav)
            res = analizar(wav, cache_dir=raiz / "cache", dialogo=texto or None, reconocedor=p.reconocedor)
        finally:
            wav.unlink(missing_ok=True)
        frames = suavizar(cues_a_frames(res.cues, res.duracion_s, FPS))

    with etapa(log, "linea_de_tiempo"):
        escenario_id = "E?" if ruta_fondo is None else carpeta_esc.name.split("_")[0]
        visemas = _a_visemas(frames)
        if len(poses_clase) > 1:
            # Provisional hasta el director (T070): recorre las poses y corta en pausas de la voz
            tomas = tomas_ciclicas(list(poses_clase), visemas, len(frames), FPS, escenario_id, p.plano,
                                   p.duracion_toma_s)
            log.info("Poses de la clase: %d tomas con %d poses", len(tomas), len(poses_clase))
        else:
            tomas = [Toma(0, escenario_id, pose.id, p.plano)]
        semilla = semilla_de_clase(clase_id, p.semilla)
        mov = pose.movimiento            # en modo de respaldo ambas amplitudes son 0: solo parpadeo
        lt = LineaDeTiempo(FPS, len(frames), semilla, visemas, tomas,
                           generar_parpadeos(len(frames), FPS, semilla),
                           calcular_hablando(visemas, len(frames)))
        lt.validar()
        anim = generar_animacion(lt.n_frames, FPS, semilla, lt.hablando, mov.respiracion_escala, mov.cabeza_px)

    fondo = None
    try:
        with etapa(log, "capas"):
            ventana = ventana_plano(pose, p.plano)
            if ruta_fondo is not None and Path(ruta_fondo).suffix.lower() == ".mp4":
                fondo = FondoVideoLayer(ruta_fondo, ventana, pose.lienzo, (W, H), FPS,
                                        desenfoque=pose.planos[p.plano].desenfoque, cache_dir=raiz / "cache")
            else:
                fondo = FondoLayer(ruta_fondo, ventana, pose.lienzo, (W, H), pose.planos[p.plano].desenfoque)
            if pose.formas is not None or len(poses_clase) > 1:
                personaje = [PersonajeLayer(poses_clase, ventana, (W, H), alinear=p.alinear)]
            else:
                anclas = AnclasEstaticas(pose)
                personaje = [CuerpoLayer(pose, ventana, (W, H)),
                             OjosLayer(pose, anclas, ventana, (W, H)),
                             BocaLayer(pose, anclas, ventana, (W, H))]
            compositor = Compositor([fondo, *personaje], (W, H))

        final = raiz / "salidas" / f"{clase_id}_{date.today():%Y%m%d}.mp4"
        with etapa(log, "render_y_encode"):
            with Codificador(final, audio, W, H, FPS, duracion_esperada_s=info.duracion_s) as enc:
                decimo = max(1, lt.n_frames // 10)
                for n in range(lt.n_frames):
                    ctx = ContextoFrame(n, n / FPS, (W, H), lt.toma_en(n), lt.visema_en(n), lt.parpadeando(n),
                                        float(anim.escala[n]), float(anim.dx[n]), float(anim.dy[n]))
                    enc.escribir(compositor.componer(ctx).tobytes())
                    if n % decimo == 0:
                        log.info("  %d %%", 100 * n // lt.n_frames)
    finally:
        if hasattr(fondo, "cerrar"):
            fondo.cerrar()                  # detiene el decodificador del video de fondo
    log.info("Listo: %s", final)
    return final


if __name__ == "__main__":
    from src.cli import main
    sys.exit(main())
