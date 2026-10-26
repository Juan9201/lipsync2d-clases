"""Render de un tramo de una clase, para revisar un detalle sin renderizar la clase entera.

Uso:  python -m src.tramo A2-M14-2 108 148 [--escenario E2]

Analiza el audio y dirige la clase completa (así las decisiones son las mismas que en el video final) y solo dibuja y codifica
los frames del tramo. Necesita que la clase ya tenga su audio en clases/. Deja `salidas/prueba_<clase>_<desde>-<hasta>s_<fecha>.mp4`
(el prefijo «prueba_» evita que el lote lo confunda con la clase terminada).
"""
import argparse
import sys
from pathlib import Path

from src import rutas
from src.lote.cola import Trabajo
from src.lote.trabajadores import parametros_de
from src.render import renderizar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("clase")
    ap.add_argument("desde", type=float)
    ap.add_argument("hasta", type=float)
    ap.add_argument("--escenario", default="")
    ap.add_argument("--idioma", default="mixto", help="es | en | mixto (elige el reconocedor de visemas)")
    a = ap.parse_args(argv)
    raiz = rutas.RAIZ
    if not (raiz / "clases" / f"{a.clase}.mp3").is_file():
        print(f"La clase {a.clase} aún no tiene audio en clases/: produce la clase una vez (genera la voz) o usa la interfaz.")
        return 2
    t = Trabajo(id=a.clase, guion=str(raiz / "clases" / f"{a.clase}.txt"), escenarios=a.escenario, idioma=a.idioma)
    p = parametros_de(t, raiz)
    p.tramo_s = (a.desde, a.hasta)
    print(renderizar(p, raiz))
    return 0


if __name__ == "__main__":
    sys.exit(main())
