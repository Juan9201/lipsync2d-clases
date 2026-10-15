"""FR-014: audios en lote, con reintentos y reanudables."""
import pytest

from src.errores import TTSNoDisponible
from src.tts.base import EstadoProveedor, OpcionesTTS, TTSReintentable
from src.tts.lote import generar_audios_en_lote


class ProveedorFalso:
    nombre = "falso"
    extension = "mp3"
    limite_caracteres = 8000
    max_reintentos = 3

    def __init__(self, fallos_transitorios=(), fallo_definitivo_en=None):
        self.llamadas = []
        self._transitorios = set(fallos_transitorios)     # nº de llamada que falla una vez
        self._definitivo = fallo_definitivo_en            # texto que falla siempre
        self._ya_fallo = set()

    def comprobar(self):
        return EstadoProveedor(True, "ok")

    def sintetizar(self, texto, destino, opciones):
        self.llamadas.append(texto)
        n = len(self.llamadas)
        if self._definitivo and self._definitivo in texto:
            raise TTSReintentable("Se alcanzó el límite de cuota", "Usa --tts piper")
        if n in self._transitorios and n not in self._ya_fallo:
            self._ya_fallo.add(n)
            raise TTSReintentable("error temporal", "reintenta")
        destino.write_bytes(b"audio:" + texto.encode())
        return destino


def _guiones(proyecto, n=3):
    carpeta = proyecto / "clases"
    for i in range(1, n + 1):
        (carpeta / f"clase_{i:04d}.txt").write_text(f"Guion número {i}.", encoding="utf-8")
    return carpeta


def test_genera_los_tres_audios_tras_un_reintento(proyecto_tmp):
    carpeta = _guiones(proyecto_tmp)
    prov = ProveedorFalso(fallos_transitorios={2})
    r = generar_audios_en_lote(carpeta, prov, OpcionesTTS(), dormir=lambda s: None)
    assert r.generados == 3 and not r.pendientes and r.error is None
    for i in (1, 2, 3):
        assert (carpeta / f"clase_{i:04d}.mp3").read_bytes().startswith(b"audio:")
    assert not list(carpeta.glob("*.part"))


def test_relanzar_no_regenera_los_existentes(proyecto_tmp):
    carpeta = _guiones(proyecto_tmp)
    prov = ProveedorFalso()
    generar_audios_en_lote(carpeta, prov, OpcionesTTS(), dormir=lambda s: None)
    antes = len(prov.llamadas)
    r = generar_audios_en_lote(carpeta, prov, OpcionesTTS(), dormir=lambda s: None)
    assert len(prov.llamadas) == antes and r.generados == 0 and r.omitidos == 3


def test_se_detiene_con_causa_si_el_proveedor_no_se_recupera(proyecto_tmp):
    carpeta = _guiones(proyecto_tmp)
    prov = ProveedorFalso(fallo_definitivo_en="número 2")
    r = generar_audios_en_lote(carpeta, prov, OpcionesTTS(), dormir=lambda s: None)
    assert r.generados == 1 and r.pendientes == ["clase_0002", "clase_0003"]
    assert isinstance(r.error, TTSNoDisponible) and "cuota" in str(r.error)
    assert (carpeta / "clase_0001.mp3").exists() and not (carpeta / "clase_0002.mp3").exists()


def test_omite_guiones_vacios_y_avisa(proyecto_tmp):
    carpeta = _guiones(proyecto_tmp, 1)
    (carpeta / "vacia.txt").write_text("[pose:P1]  ", encoding="utf-8")
    r = generar_audios_en_lote(carpeta, ProveedorFalso(), OpcionesTTS(), dormir=lambda s: None)
    assert r.generados == 1 and "vacia" in r.vacios


def test_si_ya_existe_un_wav_tambien_se_omite(proyecto_tmp):
    carpeta = _guiones(proyecto_tmp, 1)
    (carpeta / "clase_0001.wav").write_bytes(b"x")
    r = generar_audios_en_lote(carpeta, ProveedorFalso(), OpcionesTTS(), dormir=lambda s: None)
    assert r.generados == 0 and r.omitidos == 1


def test_carpeta_inexistente(proyecto_tmp):
    from src.errores import AssetInvalido
    with pytest.raises(AssetInvalido):
        generar_audios_en_lote(proyecto_tmp / "no", ProveedorFalso(), OpcionesTTS())
