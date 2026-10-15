"""Mide tiempo y pico de RAM de un render real (NFR-001, NFR-002).

Uso:  python pruebas/medicion/medir_render.py --personaje profesor --audio clase.mp3 [--guion g.txt]
Lanza `python -m src.render` como proceso aparte y vigila su memoria (incluido ffmpeg).
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parents[2]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--personaje", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("--guion")
    a, extra = p.parse_known_args()      # el resto de argumentos pasa tal cual a src.render
    cmd = [sys.executable, "-m", "src.render", "--personaje", a.personaje, "--audio", a.audio, *extra]
    if a.guion:
        cmd += ["--guion", a.guion]
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=RAIZ)
    pico, ps = 0, psutil.Process(proc.pid)
    while proc.poll() is None:
        try:
            total = ps.memory_info().rss + sum(h.memory_info().rss for h in ps.children(recursive=True))
            pico = max(pico, total)
        except psutil.Error:
            pass
        time.sleep(0.2)
    dur = time.perf_counter() - t0
    print(f"\nRESULTADO código={proc.returncode} tiempo={dur:.1f} s pico_RAM={pico / 2**20:.0f} MB")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
