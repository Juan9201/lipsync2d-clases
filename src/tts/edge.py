"""Proveedor `edge`: voces neuronales gratuitas (biblioteca edge-tts). Requiere internet."""
import asyncio
from pathlib import Path

from src.errores import TTSNoDisponible
from src.tts.base import EstadoProveedor, OpcionesTTS

VOZ_DEFECTO = "en-US-AndrewMultilingualNeural"   # multilingüe; se confirma en el spike S4
SUGERENCIA = "entrega un audio propio con --audio"


class ProveedorEdge:
    nombre = "edge"
    extension = "mp3"
    limite_caracteres = 5000
    max_reintentos = 2

    def __init__(self, voz: str = VOZ_DEFECTO):
        self.voz = voz

    def comprobar(self) -> EstadoProveedor:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return EstadoProveedor(False, "falta el paquete edge-tts (ejecuta .\\instalar.ps1)")
        return EstadoProveedor(True, "paquete instalado (requiere internet al sintetizar)")

    def sintetizar(self, texto: str, destino: Path, opciones: OpcionesTTS) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSNoDisponible("Falta el paquete edge-tts", "Ejecuta .\\instalar.ps1") from exc
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        voz = opciones.voz or self.voz

        async def guardar():
            await edge_tts.Communicate(texto, voz).save(str(destino))

        bucle = asyncio.new_event_loop()          # nuevo bucle: seguro también dentro de hilos/UI
        try:
            bucle.run_until_complete(guardar())
        except Exception as exc:                  # red, servicio o voz inválida
            destino.unlink(missing_ok=True)
            raise TTSNoDisponible(f"edge-tts no pudo generar el audio ({type(exc).__name__}: {exc})",
                                  f"Comprueba tu conexión a internet y la voz «{voz}», o {SUGERENCIA}") from exc
        finally:
            bucle.close()
        return destino
