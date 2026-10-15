"""Estado del lote (FR-105): progreso, ritmo, estimación y errores con su causa."""
from typing import Optional

from src.lote.cola import Cola


def _duracion(segundos: float) -> str:
    segundos = max(int(round(segundos)), 0)
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h} h {m} min" if h else (f"{m} min {s} s" if m else f"{s} s")


def resumen_texto(cola: Cola, lote: Optional[str] = None) -> str:
    r = cola.resumen(lote)
    nombre = f"Lote {lote}" if lote else "Todas las clases"
    lineas = [f"{nombre}: {r['total']} clases — {r['hecho']} hechas · {r['en_proceso']} en proceso · "
              f"{r['pendiente']} pendientes · {r['error']} con error"]
    hechos = cola.trabajos("hecho", lote)
    if hechos:
        inicio = min(t.inicio for t in hechos)
        fin = max(t.fin for t in hechos)
        efectivo = max(fin - inicio, 0.001) / len(hechos)
        medio = sum(t.fin - t.inicio for t in hechos) / len(hechos)
        faltan = r["pendiente"] + r["en_proceso"]
        lineas.append(f"Tiempo efectivo medio: {efectivo:.1f} s por clase (ritmo del lote); "
                      f"cada trabajo tarda {medio:.1f} s")
        lineas.append(f"Estimación para terminar: {_duracion(faltan * efectivo)} ({faltan} por hacer)")
    else:
        lineas.append("Tiempo efectivo medio: sin datos todavía. Estimación para terminar: sin datos")
    errores = cola.trabajos("error", lote)
    if errores:
        lineas.append("Errores:")
        lineas += [f"  {t.id}: {t.error[:220]}" for t in errores]
    return "\n".join(lineas)
