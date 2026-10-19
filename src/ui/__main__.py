"""python -m src.ui [--puerto 8780] [--no-abrir]: abre la interfaz local (guiones, voces, render y lote)."""
import argparse
import sys
import threading
import webbrowser

from src import rutas
from src.ui.servidor import crear_servidor


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m src.ui", description="Interfaz local del proyecto Lipsync 2D")
    p.add_argument("--puerto", type=int, default=8780)
    p.add_argument("--no-abrir", action="store_true", help="No abrir el navegador")
    args = p.parse_args(argv)
    try:
        servidor = crear_servidor(rutas.RAIZ, args.puerto)
    except OSError:
        print(f"ERROR: el puerto {args.puerto} está ocupado. Qué hacer: cierra la otra ventana de la interfaz o usa --puerto 8781")
        return 1
    url = f"http://localhost:{args.puerto}/"
    print(f"Interfaz del proyecto en {url}  (cierra esta ventana para apagarla)", flush=True)
    if not args.no_abrir:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
