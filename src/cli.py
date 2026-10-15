"""Línea de comandos (FR-070): python -m src.render ..."""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

from src import rutas
from src.errores import ErrorAccionable

RESOLUCIONES = ("1280x720", "1920x1080")
PROVEEDORES_TTS = ("gemini-studio", "edge")


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.render",
                                description="Genera el video de una clase con la boca sincronizada")
    p.add_argument("--guion", type=Path, help="Archivo .txt con el guion (opcional con --audio)")
    p.add_argument("--personaje", required=True, help="Nombre del personaje (carpeta en personajes/)")
    p.add_argument("--audio", type=Path, help="Audio propio MP3 o WAV")
    p.add_argument("--tts", choices=PROVEEDORES_TTS, default="gemini-studio",
                   help="Proveedor de voz cuando no hay --audio")
    p.add_argument("--genero", choices=("hombre", "mujer"),
                   help="Género de la voz (por defecto, el de tts.yaml; sin ajuste, hombre)")
    p.add_argument("--resolucion", choices=RESOLUCIONES, default="1280x720")
    p.add_argument("--seed", type=int, default=0, help="Semilla para que el resultado sea reproducible")
    p.add_argument("--pose", help="Pose a usar (por defecto, la primera)")
    p.add_argument("--escenario", help="Escenario a usar (por defecto, el primero)")
    p.add_argument("--reconocedor", choices=("phonetic", "pocketSphinx"), default="phonetic")
    return p


def generar_voz(guion: Optional[Path], proveedor_nombre: str, raiz: Path,
                genero: Optional[str] = None) -> Path:
    """Sin --audio: genera la voz desde el guion (FR-010) y la guarda en clases/ para reutilizarla.
    Si el proveedor falla se detiene con la causa y las alternativas (FR-013)."""
    from src.errores import AssetInvalido
    from src.registro import obtener_logger
    from src.tts import obtener_proveedor
    from src.tts.comun import sintetizar_texto
    if guion is None:
        raise ErrorAccionable("No se indicó ni --audio ni --guion",
                              "Entrega un audio propio con --audio, o un guion con --guion y --tts")
    if not Path(guion).is_file():
        raise AssetInvalido(f"El guion no existe: {guion}", "Revisa la ruta indicada en --guion")
    proveedor, opciones = obtener_proveedor(proveedor_nombre, raiz, genero)
    destino = Path(raiz) / "clases" / f"{Path(guion).stem}.{proveedor.extension}"
    log = obtener_logger("tts")
    if destino.is_file():
        log.info("Se reutiliza el audio ya generado: %s", destino)
        return destino
    log.info("Generando la voz con %s ...", proveedor.nombre)
    return sintetizar_texto(proveedor, Path(guion).read_text(encoding="utf-8"), destino, opciones)


def main(argv: Optional[List[str]] = None, raiz: Path = rutas.RAIZ) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = construir_parser().parse_args(argv)
    from src.render import ParametrosRender, renderizar   # import tardío: evita ciclos
    try:
        if args.audio is None:
            audio = generar_voz(args.guion, args.tts, raiz, args.genero)
        else:
            audio = args.audio
        ancho, alto = (int(v) for v in args.resolucion.split("x"))
        final = renderizar(ParametrosRender(
            personaje=args.personaje, audio=audio, guion=args.guion, pose=args.pose,
            escenario=args.escenario, resolucion=(ancho, alto), semilla=args.seed,
            reconocedor=args.reconocedor), raiz=raiz)
    except ErrorAccionable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Video listo: {final}")
    return 0
