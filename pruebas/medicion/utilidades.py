"""Vigila el tiempo y el pico de RAM de un proceso (incluidos sus hijos, p. ej. ffmpeg)."""
import subprocess
import time
from pathlib import Path
from typing import Sequence, Tuple

import psutil


def medir_proceso(cmd: Sequence[str], cwd: Path) -> Tuple[int, float, int]:
    """Devuelve (código de salida, segundos, pico de RAM en bytes)."""
    t0 = time.perf_counter()
    proc = subprocess.Popen(list(cmd), cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ps, pico = psutil.Process(proc.pid), 0
    while proc.poll() is None:
        try:
            total = ps.memory_info().rss + sum(h.memory_info().rss for h in ps.children(recursive=True))
            pico = max(pico, total)
        except psutil.Error:
            pass
        time.sleep(0.2)
    return proc.returncode, time.perf_counter() - t0, pico
