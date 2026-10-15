"""Errores visibles para el usuario (NFR-006): siempre en español, con la causa y la
acción que debe tomar."""


class ErrorAccionable(Exception):
    """Error con `causa` (qué pasó) y `sugerencia` (qué hacer para corregirlo)."""

    def __init__(self, causa: str, sugerencia: str):
        if not causa or not causa.strip() or not sugerencia or not sugerencia.strip():
            raise ValueError("Un error accionable necesita causa y sugerencia no vacías")
        self.causa = causa.strip()
        self.sugerencia = sugerencia.strip()
        super().__init__(f"{self.causa}. Qué hacer: {self.sugerencia}")


class EntornoIncompleto(ErrorAccionable):
    """Falta una dependencia, una descarga falló o un checksum no coincide."""


class AssetInvalido(ErrorAccionable):
    """Un asset (pose, boca, escenario, imagen) no cumple el contrato."""


class TTSNoDisponible(ErrorAccionable):
    """El proveedor de voz elegido falló (FR-013)."""
