"""Orquestador de un trabajo de render (FR-070, NFR-006): de la clase (audio + guion) al MP4.

Uso:  python -m src.render --personaje profesor --audio clases\\clase_0001.mp3 [--guion ...]
"""
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Sequence, Tuple

from src import rutas
from src.audio import convertir_para_analisis, info_audio
from src.biblioteca.validacion import validar_escenario, validar_pose
from src.animation import calcular_hablando, generar_animacion, generar_parpadeos
from src.biblioteca.modelos import cargar_escenario
from src.compositor import Compositor
from src.director import cargar_reglas, dirigir
from src.encoder import Codificador
from src.escena import config as escena_cfg_mod
from src.escena.escena import EscenaLayer
from src.errores import AssetInvalido
from src.guion import limpiar_para_analisis
from src.palabras import detectar_cuentas, tiempos_de_palabras
from src.layers.base import ContextoFrame
from src.layers.camara import ventana_plano
from src.layers.concretas import AnclasEstaticas, BocaLayer, CuerpoLayer, FondoLayer, OjosLayer
from src.layers.fondo_video import FondoVideoLayer
from src.layers.personaje import PersonajeLayer
from src.lipsync import analizar, cues_a_frames, suavizar
from src import progreso
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
    duracion_toma_s: float = 25.0      # cada cuánto cambia de pose (solo sin director)
    # --- director automático (FR-090): elige poses, planos de la cámara virtual y momentos de corte ---
    director: bool = False
    reglas: Optional[Path] = None      # archivo de reglas (por defecto, reglas_director.yaml del proyecto si existe)
    plano_inicial: Optional[str] = None
    etiqueta: Optional[str] = None     # nombre para el log, el seguimiento y los archivos de una prueba; la semilla sigue saliendo de clase_id
    tramo_s: Optional[Tuple[float, float]] = None   # (desde, hasta) en segundos: se decide y analiza la clase entera pero solo se renderiza ese tramo


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
    """Renderiza una clase y deja su seguimiento en vivo (etapas y cuadros, en ms) para la interfaz."""
    from src.progreso import con_seguimiento
    with con_seguimiento(Path(raiz), p.etiqueta or p.clase_id or Path(p.audio).stem):
        return _renderizar_clase(p, raiz)


def _renderizar_clase(p: ParametrosRender, raiz: Path = rutas.RAIZ) -> Path:
    raiz = Path(raiz)
    clase_id = p.clase_id or Path(p.audio).stem
    nombre = p.etiqueta or clase_id                    # una prueba no comparte log, seguimiento ni archivos con la clase real
    log = obtener_logger("render", archivo=raiz / "logs" / f"{nombre}.log")
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
        escena_cfg = None
        if not pose.respaldo:
            carpeta_esc = _buscar_carpeta(raiz / "escenarios", "E", p.escenario)
            if carpeta_esc is None:
                raise AssetInvalido("No hay ningún escenario disponible para esta pose",
                                    "Sube un escenario (por ejemplo E1_salon.png) a entrada/ y ejecuta "
                                    "`python -m src.biblioteca importar`")
            if escena_cfg_mod.es_escena(carpeta_esc):              # escenario con capas: fondo trasero + frente + luces
                escena_cfg = escena_cfg_mod.cargar_config(carpeta_esc)
                ruta_fondo = escena_cfg_mod.archivos_de_capas(carpeta_esc)[0]
                permitidas = escena_cfg["poses_permitidas"]
                if permitidas:                                      # el escenario puede excluir poses que no valen sentadas
                    poses_clase = {k: v for k, v in poses_clase.items() if k in permitidas}
                    if not poses_clase:
                        raise AssetInvalido(f"Ninguna pose de la clase está permitida en el escenario {carpeta_esc.name}",
                                            "Permite alguna en el editor de escenas o usa otras poses")
                    pose = next(iter(poses_clase.values()))
            else:
                ruta_fondo = validar_escenario(carpeta_esc, (W, H))
        info = info_audio(audio)
    usar_director = p.director and not pose.respaldo

    texto = ""
    if p.guion is not None and Path(p.guion).is_file():
        texto = limpiar_para_analisis(Path(p.guion).read_text(encoding="utf-8"))
    if not texto:
        log.info("Clase sin guion: se usa una sola toma y el lipsync no recibe texto de apoyo")

    with etapa(log, "rhubarb"):
        wav = raiz / "cache" / "analisis" / f"{nombre}.wav"
        try:
            convertir_para_analisis(audio, wav)
            res = analizar(wav, cache_dir=raiz / "cache", dialogo=texto or None, reconocedor=p.reconocedor)
        finally:
            wav.unlink(missing_ok=True)
        frames = suavizar(cues_a_frames(res.cues, res.duracion_s, FPS))

    with etapa(log, "linea_de_tiempo"):
        escenario_id = "E?" if ruta_fondo is None else carpeta_esc.name.split("_")[0]
        visemas = _a_visemas(frames)
        semilla = semilla_de_clase(clase_id, p.semilla)
        if usar_director:
            ruta_reglas = p.reglas or (raiz / "reglas_director.yaml" if (raiz / "reglas_director.yaml").is_file() else None)
            admite = cargar_escenario(carpeta_esc).admite if ruta_fondo is not None else None
            if escena_cfg is not None and escena_cfg["poses_permitidas"]:
                base_admite = admite
                admite = lambda pose_id, plano: pose_id in escena_cfg["poses_permitidas"] and (base_admite is None or base_admite(pose_id, plano))
            cuentas = []
            if texto and any(getattr(q, "cuenta", 0) for q in poses_clase.values()):
                pal = tiempos_de_palabras(texto, res.cues, res.duracion_s)
                cuentas = [[(i.n, round(i.t0 * FPS), round(i.t1 * FPS)) for i in sec] for sec in detectar_cuentas(texto, pal)]
                log.info("Cuentas en el guion: %d (%s)", len(cuentas), "; ".join(
                    ",".join(f"{i.palabra}@{i.t0:.1f}s" for i in sec) for sec in detectar_cuentas(texto, pal)))
            tomas = dirigir(list(poses_clase.values()), visemas, len(frames), FPS, escenario_id, semilla,
                            cargar_reglas(ruta_reglas), admite, p.plano_inicial, registro=log.info, cuentas=cuentas)
            log.info("Director: %d tomas, planos %s, poses %d", len(tomas), "/".join(sorted({t.plano for t in tomas})),
                     len({t.pose for t in tomas}))
        elif len(poses_clase) > 1:
            # Provisional hasta el director (T070): recorre las poses y corta en pausas de la voz
            tomas = tomas_ciclicas(list(poses_clase), visemas, len(frames), FPS, escenario_id, p.plano,
                                   p.duracion_toma_s)
            log.info("Poses de la clase: %d tomas con %d poses", len(tomas), len(poses_clase))
        else:
            tomas = [Toma(0, escenario_id, pose.id, p.plano)]
        mov = pose.movimiento            # en modo de respaldo ambas amplitudes son 0: solo parpadeo
        lt = LineaDeTiempo(FPS, len(frames), semilla, visemas, tomas,
                           generar_parpadeos(len(frames), FPS, semilla, cortes=[t.f0 for t in tomas]),
                           calcular_hablando(visemas, len(frames)))
        lt.validar()
        anim = generar_animacion(lt.n_frames, FPS, semilla, lt.hablando, mov.respiracion_escala, mov.cabeza_px)

    fondo = None
    try:
        with etapa(log, "capas"):
            if escena_cfg is not None:
                fondo = EscenaLayer(carpeta_esc, escena_cfg, poses_clase, (W, H), alinear=p.alinear, fps=FPS, cache_dir=raiz / "cache")
                compositor = Compositor([fondo], (W, H))
            else:
                plano_base = lt.tomas[0].plano
                ventana = ventana_plano(pose, plano_base)
                # con director, una ventana por plano usado: la cámara virtual cambia de plano en cada toma
                planos = sorted({t.plano for t in lt.tomas}) if usar_director else []
                ventanas = {pl: ventana_plano(pose, pl) for pl in planos} or None
                desenfoques = {pl: pose.planos[pl].desenfoque for pl in planos} or None
                if ruta_fondo is not None and Path(ruta_fondo).suffix.lower() == ".mp4":
                    fondo = FondoVideoLayer(ruta_fondo, ventana, pose.lienzo, (W, H), FPS,
                                            desenfoque=pose.planos[plano_base].desenfoque, cache_dir=raiz / "cache",
                                            ventanas=ventanas, desenfoques=desenfoques)
                else:
                    fondo = FondoLayer(ruta_fondo, ventana, pose.lienzo, (W, H), pose.planos[plano_base].desenfoque,
                                       ventanas, desenfoques)
                if pose.formas is not None or len(poses_clase) > 1 or usar_director:
                    personaje = [PersonajeLayer(poses_clase, ventanas or ventana, (W, H), alinear=p.alinear)]
                else:
                    anclas = AnclasEstaticas(pose)
                    personaje = [CuerpoLayer(pose, ventana, (W, H)),
                                 OjosLayer(pose, anclas, ventana, (W, H)),
                                 BocaLayer(pose, anclas, ventana, (W, H))]
                compositor = Compositor([fondo, *personaje], (W, H))

        final = raiz / "salidas" / f"{clase_id}_{date.today():%Y%m%d}.mp4"
        f0, f1, audio_salida, duracion_salida = 0, lt.n_frames, audio, info.duracion_s
        if p.tramo_s is not None:
            f0 = max(0, min(lt.n_frames - 1, round(p.tramo_s[0] * FPS)))
            f1 = max(f0 + 1, min(lt.n_frames, round(p.tramo_s[1] * FPS)))
            final = raiz / "salidas" / f"{nombre}_{date.today():%Y%m%d}.mp4"
            audio_salida = raiz / "cache" / "analisis" / f"{nombre}_tramo.wav"
            subprocess.run([str(rutas.FFMPEG), "-v", "error", "-y", "-ss", f"{f0 / FPS:.3f}", "-t", f"{(f1 - f0) / FPS:.3f}",
                            "-i", str(audio), str(audio_salida)], check=True)
            duracion_salida = (f1 - f0) / FPS
            log.info("Tramo de prueba: frames %d-%d (%.1f-%.1f s)", f0, f1, f0 / FPS, f1 / FPS)
        with etapa(log, "render_y_encode"):
            with Codificador(final, audio_salida, W, H, FPS, duracion_esperada_s=duracion_salida) as enc:
                decimo = max(1, (f1 - f0) // 10)
                for n in range(f0, f1):
                    previa, mezcla = lt.mezcla_en(n)
                    ctx = ContextoFrame(n, n / FPS, (W, H), lt.toma_en(n), lt.visema_en(n), lt.parpadeando(n),
                                        float(anim.escala[n]), float(anim.dx[n]), float(anim.dy[n]),
                                        lt.fase_ojos(n), previa, mezcla)
                    enc.escribir(compositor.componer(ctx).tobytes())
                    progreso.avance(n - f0 + 1, f1 - f0)
                    if (n - f0) % decimo == 0:
                        log.info("  %d %%", 100 * (n - f0) // (f1 - f0))
    finally:
        if hasattr(fondo, "cerrar"):
            fondo.cerrar()                  # detiene el decodificador del video de fondo
    log.info("Listo: %s", final)
    return final


if __name__ == "__main__":
    from src.cli import main
    sys.exit(main())
