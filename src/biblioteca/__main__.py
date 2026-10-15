"""python -m src.biblioteca importar [--entrada entrada] [--personaje profesor]"""
import argparse
import sys
from pathlib import Path

from src import rutas
from src.biblioteca.importador import importar


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m src.biblioteca",
                                description="Gestión de la biblioteca de poses y escenarios")
    sub = p.add_subparsers(dest="orden", required=True)
    imp = sub.add_parser("importar", help="Clasifica y valida los archivos de entrada/")
    imp.add_argument("--entrada", type=Path, default=rutas.RAIZ / "entrada")
    imp.add_argument("--personaje", default="profesor")
    args = p.parse_args(argv)
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
