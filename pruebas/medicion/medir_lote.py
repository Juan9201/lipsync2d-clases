"""Mide el rendimiento de un lote real (NFR-007, NFR-008, NFR-009) con tus assets del proyecto.

Uso:  python pruebas/medicion/medir_lote.py --clases 4 --trabajadores 4 [--minutos 5]
Crea N clases a partir de tts_008.mp3 (recortado a --minutos), las procesa en un lote aparte
(lote/medicion.db) y borra los videos de prueba al terminar.
"""
import argparse
import sys
import threading
import time
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from pruebas.utiles import EJEMPLO, concatenar, recortar_audio       # noqa: E402
from src.lote.cola import Cola                                       # noqa: E402
from src.lote.manifiesto import crear_manifiesto, encolar_manifiesto  # noqa: E402
from src.lote.trabajadores import correr                             # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--clases", type=int, default=4)
    p.add_argument("--trabajadores", type=int, default=4)
    p.add_argument("--minutos", type=float, default=5)
    p.add_argument("--personaje", default="profesor")
    a = p.parse_args()

    carpeta = RAIZ / "cache" / "medicion_lote"
    carpeta.mkdir(parents=True, exist_ok=True)
    for f in carpeta.glob("*"):
        f.unlink()
    segundos = a.minutos * 60
    base = EJEMPLO if segundos <= 280 else concatenar([EJEMPLO] * int(segundos // 280 + 1), RAIZ / "cache" / "medicion_base.mp3")   # fuera de la carpeta del lote
    for i in range(1, a.clases + 1):
        recortar_audio(base, carpeta / f"medicion_{i:02d}.mp3", segundos)
        (carpeta / f"medicion_{i:02d}.txt").write_text("Clase de medición.", encoding="utf-8")
    csv_ruta = carpeta / "medicion.csv"
    crear_manifiesto(carpeta, a.personaje, "medicion", csv_ruta, poses="P1", escenarios="E1")
    db = RAIZ / "lote" / "medicion.db"
    for suf in ("", "-wal", "-shm"):
        Path(str(db) + suf).unlink(missing_ok=True)
    cola = Cola(db)
    encolar_manifiesto(cola, csv_ruta, RAIZ)

    pico, activo = [0], [True]

    def vigilar():
        yo = psutil.Process()
        while activo[0]:
            try:
                pico[0] = max(pico[0], sum(h.memory_info().rss for h in yo.children(recursive=True)))
            except psutil.Error:
                pass
            time.sleep(0.5)

    hilo = threading.Thread(target=vigilar, daemon=True)
    hilo.start()
    t0 = time.perf_counter()
    codigo = correr(RAIZ, db, a.trabajadores, 1, intervalo_s=15)
    total = time.perf_counter() - t0
    activo[0] = False
    hechos = cola.trabajos("hecho")
    tam = [Path(t.salida).stat().st_size for t in hechos if Path(t.salida).exists()]
    print(f"\nRESULTADO código={codigo} · {len(hechos)}/{a.clases} clases de {a.minutos:g} min con {a.trabajadores} "
          f"trabajadores · total {total:.0f} s · {total / max(len(hechos), 1):.1f} s efectivos por clase · "
          f"pico RAM total {pico[0] / 2**20:.0f} MB · MP4 medio {sum(tam) / max(len(tam), 1) / 2**20:.1f} MB")
    for t in hechos:
        Path(t.salida).unlink(missing_ok=True)
    for f in carpeta.glob("*"):
        f.unlink()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
