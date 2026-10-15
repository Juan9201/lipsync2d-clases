# Contrato: interfaz de proveedor TTS

Módulo `src/tts`. Proveedores intercambiables: `gemini-studio` (defecto) y `edge`. (Piper se retiró el 2026-10-14 por calidad de voz.)

```python
class ProveedorTTS(Protocol):
    nombre: str                                   # "gemini-studio" | "edge"

    def comprobar(self) -> EstadoProveedor:       # sin efectos; usado por FR-002 y FR-013
        ...                                       # EstadoProveedor(ok: bool, detalle: str)

    def sintetizar(self, texto: str, destino: Path,
                   opciones: OpcionesTTS) -> Path:
        """Escribe el audio (MP3 o WAV) en `destino` y lo devuelve.
        Lanza TTSNoDisponible(causa, sugerencia) ante cualquier fallo (FR-013)."""
```

`OpcionesTTS`: `voz`, `idioma` (def. `es-ES`), `estilo`, `velocidad`, `tono`,
`temperatura`, `modelo`. Cada proveedor usa las que le aplican e ignora el resto.

## Pre y postprocesado común (módulo `tts`, no del proveedor)
1. **Limpieza (FR-012):** se eliminan las etiquetas de toma por prefijo reservado
   (`[toma:`, `[pose:`, `[escenario:`, `[plano:`). Otras marcas entre corchetes
   (p. ej. `[short pause]`) se conservan.
2. **Normalización del texto** para el TTS: espacios, saltos de línea; números, siglas
   y abreviaturas se expanden solo si `normalizar: true` (caso borde de la spec).
3. **Partición:** si `len(texto) > limite_caracteres` del proveedor (Gemini Studio:
   8000; configurable más bajo, p. ej. 3000, si se confirma un tope de ≈ 60 s), se parte
   por frases y se unen los audios resultantes con ffmpeg sin alterar su contenido.
4. **Reintentos:** ante 429/502 o error de red, hasta 5 reintentos con espera
   exponencial (2, 4, 8, 16, 32 s, con variación aleatoria) antes de fallar.

## Errores (mensajes en español, NFR-006)
`TTSNoDisponible` incluye siempre `causa` y `sugerencia`:

| Situación | Causa | Sugerencia |
|---|---|---|
| Webapp apagada | No se pudo conectar con gemini-tts-studio en 127.0.0.1:5055 | Inicia la webapp (`start.bat`) o entrega `--audio` |
| Sin key (`has_key: false`) | La webapp no tiene API key | Añade la key en su `.env` o desde su panel |
| 429 (cuota) | Se alcanzó el límite de cuota de Gemini | Espera al reinicio de la cuota, activa la facturación de la cuenta de Gemini, o entrega un audio propio |
| Sin internet (`edge`) | No hay conexión | Entrega un audio propio con `--audio` |

## Proveedor `gemini-studio`
- Cliente HTTP a `http://127.0.0.1:5055` (configurable). Comprueba con `GET /api/health`.
- `POST /api/generate-tts` con `{text, model, voice, language, style, temperature,
  speed, pitch}`; luego `GET /api/audio/{file}` para descargar el MP3 devuelto.
- **Serializa** las peticiones (un candado): la webapp numera los archivos listando la
  carpeta y no es segura ante peticiones simultáneas.
- No modifica ni copia nada de la webapp; no maneja la API key.

## Proveedor `edge`
Biblioteca `edge-tts`; voz por defecto en español a fijar en el spike S4 (la variante la
elige el usuario; ver spec sección 12). Requiere internet.

## Generación de audios en lote (cambio de spec propuesto CP-1)
`python -m src.tts lote --carpeta clases --proveedor gemini-studio`: para cada
`clases/<id>.txt` sin `<id>.mp3` genera el audio, con reintentos, reanudable (salta los
ya generados) y registro de progreso.

## Género de la voz (FR-015)
`tts.yaml` define `genero: hombre | mujer` y, por proveedor, `voces: {hombre: ..., mujer: ...}`.
Prioridad: `--genero` (CLI) > `genero` (archivo) > hombre. Una `voz:` explícita manda sobre el género.
Voces por defecto en Gemini: hombre `es-419-podcaster-3` (elegida por el usuario), mujer
`es-419-podcaster-2` (sin probar).
