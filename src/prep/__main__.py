"""Preparación de assets desde una imagen única.

  python -m src.prep pose P1 [--respaldo] [--boca x,y,ancho[,angulo]] [--ojos x,y,ancho[,angulo]]
  python -m src.prep pose P1 --mascara mi_mascara.png         (reimporta una máscara corregida a mano)
  python -m src.prep escenario E1 --desde P1 [--nombre salon]  (fondo limpio con inpainting)
"""
import argparse
import re
import sys
from pathlib import Path

from src import rutas
from src.errores import ErrorAccionable
from src.prep.respaldo import crear_pose_respaldo


def _tripleta(texto: str):
    try:
        valores = tuple(float(v) for v in texto.split(","))
        if len(valores) not in (3, 4):
            raise ValueError
        return valores
    except ValueError:
        raise argparse.ArgumentTypeError("usa el formato x,y,ancho[,angulo] (por ejemplo 1516,306,60,12)")


def _carpeta_pose(personaje: str, id_pose: str) -> Path:
    poses = rutas.RAIZ / "personajes" / personaje / "poses"
    for d in sorted(poses.glob("P*")) if poses.is_dir() else []:
        if re.match(rf"^{re.escape(id_pose)}(_|$)", d.name):
            return d
    return poses / id_pose


def _imagen_base(carpeta: Path) -> Path:
    ajustada = carpeta / "base_16x9.png"
    return ajustada if ajustada.is_file() else carpeta / "original.png"


def _comando_pose(args) -> int:
    from src.prep.segmentar import MODELO_DEFECTO, preparar_pose_segmentada, reimportar_mascara
    carpeta = _carpeta_pose(args.personaje, args.id)
    original = carpeta / "original.png"
    if not original.is_file():
        raise ErrorAccionable(f"No se encontró {original}",
                              f"Suelta {args.id}_<nombre>.png en entrada/ y ejecuta "
                              "`python -m src.biblioteca importar`")
    if args.mascara:
        reimportar_mascara(carpeta, args.mascara)
        print("Máscara reimportada y cuerpo.png regenerado.")
        return 0
    if args.respaldo:
        r = crear_pose_respaldo(original, carpeta, args.id, args.boca, args.ojos,
                                modo_formato=args.formato, forzar=args.forzar)
        print("Pose preparada en modo de respaldo." if r.creada else "Sin cambios.")
    else:
        r = preparar_pose_segmentada(original, carpeta, args.id, args.boca, args.ojos,
                                     modelo=args.modelo or MODELO_DEFECTO, modo_formato=args.formato,
                                     forzar=args.forzar)
        print("Pose preparada (personaje separado del fondo)." if r.creada else "Sin cambios.")
        if r.creada:
            print(f"  La máscara quedó en {carpeta / 'mascara.png'}: revísala y, si hace falta, corrígela "
                  f"en un editor y reimpórtala con --mascara.")
    for a in r.avisos:
        print(f"  AVISO  {a}")
    return 0


def _comando_escenario(args) -> int:
    from src.prep.inpainting import crear_escenario
    carpeta = _carpeta_pose(args.personaje, args.desde)
    base, mascara = _imagen_base(carpeta), carpeta / "mascara.png"
    nombre = f"{args.id}_{args.nombre}" if args.nombre else args.id
    destino = rutas.RAIZ / "escenarios" / nombre / "fondo.png"
    if destino.is_file() and not args.forzar:
        print(f"El escenario {nombre} ya estaba preparado; no se repite (usa --forzar para rehacerlo).")
        return 0
    crear_escenario(base, mascara, destino, args.margen)
    print(f"Escenario listo: {destino}")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m src.prep", description="Preparación de assets")
    sub = p.add_subparsers(dest="orden", required=True)
    pose = sub.add_parser("pose", help="Prepara una pose desde su imagen original")
    pose.add_argument("id", help="Identificador de la pose, por ejemplo P1")
    pose.add_argument("--personaje", default="profesor")
    pose.add_argument("--respaldo", action="store_true",
                      help="Modo de respaldo: la imagen completa como base (sin separar al personaje)")
    pose.add_argument("--mascara", type=Path, help="Reimporta una máscara corregida a mano")
    pose.add_argument("--modelo", help="Modelo de segmentación (por defecto birefnet-general)")
    pose.add_argument("--boca", type=_tripleta, help="Ancla de la boca: x,y,ancho[,angulo en grados antihorario]")
    pose.add_argument("--ojos", type=_tripleta, help="Ancla de los ojos: x,y,ancho[,angulo en grados antihorario]")
    pose.add_argument("--formato", choices=("recortar", "rellenar"), default="recortar")
    pose.add_argument("--forzar", action="store_true", help="Rehace la preparación aunque ya exista")
    oj = sub.add_parser("ojos", help="Rehace los ojos cerrados de prueba desde la imagen de la pose")
    oj.add_argument("id", help="Identificador de la pose, por ejemplo P1")
    oj.add_argument("--personaje", default="profesor")
    oj.add_argument("--ojos", type=_tripleta, help="Nueva ancla de los ojos: x,y,ancho[,angulo]")
    esc = sub.add_parser("escenario", help="Crea un escenario limpio (inpainting) desde una pose")
    esc.add_argument("id", help="Identificador del escenario, por ejemplo E1")
    esc.add_argument("--desde", required=True, help="Pose de la que sale la imagen, por ejemplo P1")
    esc.add_argument("--nombre", help="Nombre del escenario, por ejemplo salon")
    esc.add_argument("--personaje", default="profesor")
    esc.add_argument("--margen", type=int, default=15, help="Margen en píxeles alrededor del personaje")
    esc.add_argument("--forzar", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.orden == "ojos":
            from src.prep.ojos import regenerar_ojos
            regenerar_ojos(_carpeta_pose(args.personaje, args.id), args.ojos)
            print("Ojos cerrados de prueba regenerados.")
            return 0
        return _comando_pose(args) if args.orden == "pose" else _comando_escenario(args)
    except ErrorAccionable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
