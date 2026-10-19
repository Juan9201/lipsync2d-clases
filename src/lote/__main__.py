"""python -m src.lote crear|encolar|correr|estado|reintentar

  crear     --carpeta clases --personaje profesor --lote 2026-10-A   (genera el manifiesto CSV)
  encolar   lote\\manifiestos\\2026-10-A.csv
  correr    --trabajadores 4 --espacio-minimo-gb 20 [--lote 2026-10-A]
  estado    [--lote 2026-10-A]
  reintentar [--lote 2026-10-A]                                       (las clases con error vuelven a la cola)
"""
import argparse
import sys
from pathlib import Path

from src import rutas
from src.errores import ErrorAccionable
from src.lote.cola import Cola
from src.lote.estado import resumen_texto
from src.lote.manifiesto import crear_manifiesto, encolar_manifiesto

DB = rutas.RAIZ / "lote" / "cola.db"


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m src.lote", description="Producción en lote")
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--db", type=Path, default=DB, help="Archivo de la cola (por defecto lote/cola.db)")
    comun.add_argument("--raiz", type=Path, default=rutas.RAIZ, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="orden", required=True)
    c = sub.add_parser("crear", parents=[comun], help="Crea el manifiesto de lote desde una carpeta de guiones y audios")
    c.add_argument("--carpeta", type=Path, default=rutas.RAIZ / "clases")
    c.add_argument("--personaje", default="profesor")
    c.add_argument("--lote", required=True, help="Etiqueta del lote, por ejemplo 2026-10-A")
    c.add_argument("--poses", default="", help="Poses permitidas separadas por ;")
    c.add_argument("--escenarios", default="", help="Escenarios permitidos separados por ;")
    c.add_argument("--idioma", default="es", choices=("es", "en", "mixto"),
                   help="Idioma de las clases (decide el reconocedor de visemas; por defecto es)")
    c.add_argument("--salida", type=Path, help="Archivo CSV (por defecto lote/manifiestos/<lote>.csv)")
    e = sub.add_parser("encolar", parents=[comun], help="Crea los trabajos de un manifiesto")
    e.add_argument("manifiesto", type=Path)
    r = sub.add_parser("correr", parents=[comun], help="Procesa la cola con varios trabajadores en paralelo")
    r.add_argument("--trabajadores", type=int, default=4)
    r.add_argument("--espacio-minimo-gb", type=float, default=20)
    r.add_argument("--lote")
    s = sub.add_parser("estado", parents=[comun], help="Progreso, ritmo, estimación y errores")
    s.add_argument("--lote")
    t = sub.add_parser("reintentar", parents=[comun], help="Devuelve a la cola las clases con error")
    t.add_argument("--lote")
    w = sub.add_parser("trabajador", parents=[comun], help="(interno) un trabajador de la cola")
    w.add_argument("--espacio-minimo-gb", type=float, default=20)
    w.add_argument("--lote")
    args = p.parse_args(argv)
    try:
        if args.orden == "crear":
            destino = args.salida or rutas.RAIZ / "lote" / "manifiestos" / f"{args.lote}.csv"
            inf = crear_manifiesto(args.carpeta, args.personaje, args.lote, destino, args.poses, args.escenarios,
                                   args.idioma)
            print(f"Manifiesto creado: {destino}  ({inf.filas} clases)")
            if inf.sin_audio:
                print(f"  AVISO  {len(inf.sin_audio)} guiones sin audio (se generará con el TTS al correr): "
                      + ", ".join(inf.sin_audio[:8]) + (" …" if len(inf.sin_audio) > 8 else ""))
            if inf.sin_guion:
                print(f"  AVISO  {len(inf.sin_guion)} audios sin guion (se renderizan sin texto de apoyo): "
                      + ", ".join(inf.sin_guion[:8]) + (" …" if len(inf.sin_guion) > 8 else ""))
        elif args.orden == "encolar":
            nuevos, dup = encolar_manifiesto(Cola(args.db), args.manifiesto, args.raiz)
            print(f"{nuevos} trabajos encolados." + (f" {len(dup)} ya estaban en la cola y se ignoraron." if dup else ""))
        elif args.orden == "correr":
            from src.lote.trabajadores import correr
            return correr(args.raiz, args.db, args.trabajadores, args.espacio_minimo_gb, args.lote)
        elif args.orden == "estado":
            print(resumen_texto(Cola(args.db), args.lote))
        elif args.orden == "reintentar":
            print(f"{Cola(args.db).reintentar_errores(args.lote)} clases vuelven a la cola.")
        elif args.orden == "trabajador":
            from src.lote.trabajadores import procesar_cola
            procesar_cola(Cola(args.db), args.raiz, espacio_minimo_gb=args.espacio_minimo_gb, lote=args.lote)
    except ErrorAccionable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
