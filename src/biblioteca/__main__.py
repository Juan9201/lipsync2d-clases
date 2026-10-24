"""python -m src.biblioteca importar [--entrada entrada] [--personaje profesor]"""
import argparse
import sys
from pathlib import Path

from src import rutas
from src.biblioteca.importador import importar


def _importar_poses(args) -> int:
    from src.biblioteca.calibraciones import importar_poses
    from src.errores import ErrorAccionable
    pares = {}
    for opcion, lista in (("--bocas", args.bocas), ("--parpadeos", args.parpadeos)):
        pares[opcion] = {}
        for par in lista:
            vista, _, carpeta = par.partition("=")
            if not vista or not carpeta:
                print(f"ERROR: «{par}» no tiene el formato VISTA=CARPETA. Qué hacer: por ejemplo "
                      f"{opcion} tres_cuartos_der=C:\\ruta\\carpeta", file=sys.stderr)
                return 1
            pares[opcion][vista.strip()] = Path(carpeta.strip())
    try:
        inf = importar_poses(args.origen, args.raiz, args.personaje, args.calibraciones, pares["--bocas"],
                             pares["--parpadeos"], args.parpadeo_mascara, args.erosion_px)
    except ErrorAccionable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for linea in inf.importados:
        print(f"  OK  {linea}")
    for r in inf.rechazados:
        print(f"  NO  {r.archivo}: {r.motivo}")
    for a in inf.avisos:
        print(f"  AVISO  {a}")
    n = sum(1 for i in inf.importados if not i.startswith("bocas "))
    print(f"\n{n} importadas, {len(inf.rechazados)} rechazadas.")
    return 0 if not inf.rechazados else 2


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m src.biblioteca",
                                description="Gestión de la biblioteca de poses y escenarios")
    sub = p.add_subparsers(dest="orden", required=True)
    imp = sub.add_parser("importar", help="Clasifica y valida los archivos de entrada/")
    imp.add_argument("--entrada", type=Path, default=rutas.RAIZ / "entrada")
    imp.add_argument("--personaje", default="profesor")
    ip = sub.add_parser("importar-poses", help="Importa poses <vista>_<gesto>_<NN>.png y su calibración de bocas")
    ip.add_argument("--origen", type=Path, nargs="+", required=True, help="Carpeta(s) con las imágenes de las poses")
    ip.add_argument("--calibraciones", type=Path, help="JSON exportado por el calibrador de bocas")
    ip.add_argument("--bocas", action="append", default=[], metavar="VISTA=CARPETA",
                    help="Carpeta con las 9 bocas de una vista (repetible): tres_cuartos_der=ruta")
    ip.add_argument("--parpadeos", action="append", default=[], metavar="VISTA=CARPETA",
                    help="Carpeta con las imágenes de parpadeo de una vista (repetible); usa los recuadros del "
                         "JSON del Editor de poses: frontal=ruta")
    ip.add_argument("--parpadeo-mascara", choices=("rectangulo", "contorno"), default=None,
                    help="Forma de la zona que cambia al parpadear: el recuadro del editor o el contorno del rostro (de pelo a quijada, difuminado)")
    ip.add_argument("--erosion-px", type=float, default=None, help="Con «contorno»: cuántos píxeles se mete el corte hacia dentro del borde (por defecto 8)")
    ip.add_argument("--personaje", default="profesor")
    ip.add_argument("--raiz", type=Path, default=rutas.RAIZ, help="Raíz del proyecto (por defecto, esta carpeta)")
    args = p.parse_args(argv)
    if args.orden == "importar-poses":
        return _importar_poses(args)
    if not args.entrada.is_dir():
        print(f"ERROR: no existe la carpeta de entrada {args.entrada}. Qué hacer: créala y suelta ahí tus archivos",
              file=sys.stderr)
        return 1
    inf = importar(args.entrada, rutas.RAIZ, args.personaje)
    for linea in inf.importados:
        print(f"  OK  {linea}")
    for r in inf.rechazados:
        print(f"  NO  {r.archivo}: {r.motivo}")
    for a in inf.avisos:
        print(f"  AVISO  {a}")
    print(f"\n{len(inf.importados)} importados, {len(inf.rechazados)} rechazados.")
    return 0 if not inf.rechazados else 2


if __name__ == "__main__":
    sys.exit(main())
