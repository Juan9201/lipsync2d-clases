"""python -m src.tts lote|uno|comprobar ..."""
import argparse
import sys
from pathlib import Path

from src import rutas
from src.errores import ErrorAccionable
from src.tts import PROVEEDORES, obtener_proveedor
from src.tts.comun import sintetizar_texto
from src.tts.lote import generar_audios_en_lote


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m src.tts", description="Generación de audio desde guiones")
    sub = p.add_subparsers(dest="orden", required=True)
    for nombre, ayuda in (("lote", "Genera <id>.mp3 junto a cada <id>.txt de una carpeta (reanudable)"),
                          ("uno", "Genera el audio de un solo guion"),
                          ("comprobar", "Comprueba que el proveedor está disponible")):
        s = sub.add_parser(nombre, help=ayuda)
        s.add_argument("--proveedor", choices=PROVEEDORES, default="gemini-studio")
        s.add_argument("--genero", choices=("hombre", "mujer"), help="Género de la voz (defecto: tts.yaml)")
    sub.choices["lote"].add_argument("--carpeta", type=Path, default=rutas.RAIZ / "clases")
    sub.choices["uno"].add_argument("--guion", type=Path, required=True)
    sub.choices["uno"].add_argument("--salida", type=Path)
    args = p.parse_args(argv)
    try:
        proveedor, opciones = obtener_proveedor(args.proveedor, genero=args.genero)
        if args.orden == "comprobar":
            estado = proveedor.comprobar()
            print(("OK: " if estado.ok else "NO DISPONIBLE: ") + estado.detalle)
            return 0 if estado.ok else 1
        if args.orden == "uno":
            salida = args.salida or args.guion.with_suffix("." + proveedor.extension)
            sintetizar_texto(proveedor, args.guion.read_text(encoding="utf-8"), salida, opciones)
            print(f"Audio listo: {salida}")
            return 0
        r = generar_audios_en_lote(args.carpeta, proveedor, opciones)
    except ErrorAccionable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"\nGenerados: {r.generados} · ya existían: {r.omitidos} · sin texto: {len(r.vacios)} · "
          f"pendientes: {len(r.pendientes)}")
    if r.error:
        print(f"Se detuvo: {r.error}\nVuelve a ejecutar el mismo comando para reanudar.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
