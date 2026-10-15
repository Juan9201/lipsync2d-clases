"""FR-100, FR-102, FR-104: cola persistente en SQLite, reclamo atómico entre procesos, estados."""
import subprocess
import sys
import time

import pytest

from pruebas.utiles import RAIZ
from src.lote.cola import Cola, Trabajo


def _trabajos(n, lote="L1"):
    return [Trabajo(id=f"clase_{i:04d}", lote=lote) for i in range(1, n + 1)]


def test_los_trabajos_persisten_al_cerrar_y_reabrir(proyecto_tmp):
    ruta = proyecto_tmp / "lote" / "cola.db"
    Cola(ruta).encolar(_trabajos(5))
    reabierta = Cola(ruta)
    assert [t.id for t in reabierta.trabajos()] == [f"clase_{i:04d}" for i in range(1, 6)]
    assert all(t.estado == "pendiente" for t in reabierta.trabajos())


def test_los_duplicados_se_ignoran_y_se_informan(proyecto_tmp):
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    assert cola.encolar(_trabajos(3)) == (3, [])
    nuevos, duplicados = cola.encolar(_trabajos(5))
    assert nuevos == 2 and duplicados == ["clase_0001", "clase_0002", "clase_0003"]
    assert len(cola.trabajos()) == 5


def test_ciclo_de_vida_de_un_trabajo(proyecto_tmp):
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    cola.encolar(_trabajos(2))
    t = cola.reclamar()
    assert t.id == "clase_0001" and t.estado == "en_proceso"
    cola.terminar(t.id, "salidas/x.mp4")
    hecho = next(x for x in cola.trabajos() if x.id == t.id)
    assert hecho.estado == "hecho" and hecho.salida == "salidas/x.mp4" and hecho.fin >= hecho.inicio > 0
    t2 = cola.reclamar()
    cola.fallar(t2.id, "Audio dañado. Qué hacer: genera otro")
    err = next(x for x in cola.trabajos() if x.id == t2.id)
    assert err.estado == "error" and err.intentos == 1 and "Audio dañado" in err.error
    assert cola.reclamar() is None


def test_reclamar_respeta_el_filtro_de_lote(proyecto_tmp):
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    cola.encolar(_trabajos(2, "A") + [Trabajo(id="b1", lote="B")])
    assert cola.reclamar("B").id == "b1"
    assert cola.reclamar("B") is None


def test_los_huerfanos_con_latido_vencido_vuelven_a_pendiente(proyecto_tmp):
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    cola.encolar(_trabajos(3))
    viejo, fresco = cola.reclamar(), cola.reclamar()
    cola._forzar_latido(viejo.id, time.time() - 600)          # el proceso murió hace 10 min
    recuperados = cola.recuperar_huerfanos(max_edad_s=60)
    assert recuperados == [viejo.id]
    estados = {t.id: t.estado for t in cola.trabajos()}
    assert estados[viejo.id] == "pendiente" and estados[fresco.id] == "en_proceso"


def test_reintentar_errores(proyecto_tmp):
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    cola.encolar(_trabajos(2))
    cola.fallar(cola.reclamar().id, "fallo")
    assert cola.reintentar_errores() == 1
    assert [t.estado for t in cola.trabajos()] == ["pendiente", "pendiente"]


def test_resumen_por_estado_y_lote(proyecto_tmp):
    cola = Cola(proyecto_tmp / "lote" / "cola.db")
    cola.encolar(_trabajos(4, "A") + _trabajos(2, "B")[:0] + [Trabajo(id="b1", lote="B")])
    a = cola.reclamar("A"); cola.terminar(a.id, "x")
    b = cola.reclamar("A"); cola.fallar(b.id, "mal")
    cola.reclamar("A")
    r = cola.resumen("A")
    assert r == {"pendiente": 1, "en_proceso": 1, "hecho": 1, "error": 1, "total": 4} or \
        (r["hecho"], r["error"], r["en_proceso"], r["pendiente"], r["total"]) == (1, 1, 1, 1, 4)
    assert cola.resumen()["total"] == 5


def test_reclamo_atomico_entre_procesos(proyecto_tmp):
    """Tres procesos reclamando a la vez: cada trabajo lo toma exactamente uno."""
    ruta = proyecto_tmp / "lote" / "cola.db"
    Cola(ruta).encolar(_trabajos(36))
    codigo = ("import sys; sys.path.insert(0, r'{}'); from src.lote.cola import Cola\n"
              "c = Cola(r'{}')\n"
              "while (t := c.reclamar()) is not None:\n"
              "    print(t.id, flush=True); c.terminar(t.id, 'ok')\n").format(RAIZ, ruta)
    procesos = [subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True) for _ in range(3)]
    reclamados = []
    for p in procesos:
        salida, _ = p.communicate(timeout=60)
        assert p.returncode == 0
        reclamados += salida.split()
    assert len(reclamados) == 36 and len(set(reclamados)) == 36
    assert Cola(ruta).resumen()["hecho"] == 36
