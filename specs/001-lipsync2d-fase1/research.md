# Investigación (research.md): Lipsync 2D, Fase 1

**Fecha:** 2026-10-13 · **Spec:** v2 aprobada · **Estado:** borrador para aprobación
Convención: **[MEDIDO]** = medido hoy en este equipo; **[LEÍDO]** = leído del código del
usuario; **[SIN VERIFICAR]** = hipótesis que debe confirmarse con un *spike* (tarea
técnica corta) antes de depender de ella. No hay nada afirmado sin una de estas marcas
cuando importa.

---

## 1. Entorno del equipo [MEDIDO]

| Elemento | Hallazgo | Consecuencia |
|---|---|---|
| CPU / RAM | Ryzen 5 5600 (6 núcleos, 12 hilos), 64 GB | Caben 4–5 trabajadores de render en paralelo. |
| GPU | RTX 3050 8 GB, driver 591.86 | Útil solo para preparar assets (una vez). |
| Python | 3.11.9 (también 3.12 y 3.14) | Se usa 3.11, como pide el stack; venv propio. |
| ffmpeg | 9.0.1 (gyan.dev, WinGet) con `libx264` y `h264_nvenc` | El instalador igualmente fija su propio ffmpeg (P4). |
| NVENC | **No funciona**: ffmpeg 9.0.1 exige driver ≥ 610, hay 591.86 | Se descarta NVENC (ver §6); no hace falta actualizar el driver. |
| Disco C: | 1.157 GB libres | Sobra para los ≈ 460 GB estimados; el usuario fija 700 GB. |
| Git / Node | 2.48.1 / 24.16 | Sin uso en la Fase 1. |

## 2. Webapp `gemini-tts-studio` [LEÍDO, solo lectura]

**Qué es:** FastAPI local en `http://127.0.0.1:5055` (solo escucha en 127.0.0.1) con una
interfaz estática. Dependencias: `fastapi`, `uvicorn`, `python-dotenv`, `google-genai`,
`lameenc`.

**Sí tiene API HTTP**, pese a que el usuario creía que no existían: la interfaz web la
consume y el adaptador `gemini-studio` puede usar los mismos endpoints, sin modificar
la webapp:

| Endpoint | Uso para este proyecto |
|---|---|
| `GET /api/health` | Comprobar que la webapp está viva y tiene API key (`has_key`). Devuelve también `output_dir`. |
| `GET /api/voices?language=es-ES` | Catálogo de voces (para elegir y validar la voz). |
| `POST /api/generate-tts` | Cuerpo: `text` (1–8000 caracteres), `model`, `voice` (def. `Kore`), `language` (def. `es-ES`), `style`, `temperature`, `speed`, `pitch`. Devuelve `{file, url, style_applied, size_kb}`. |
| `GET /api/audio/tts_NNN.mp3` | Descargar el MP3 generado. |

**Cómo se configuran las voces:** por petición (`voice`, `language`, `style`,
`speed`, `pitch`); `speed` y `pitch` se traducen a una instrucción de estilo en texto.
Modelos: `gemini-3.8-flash-tts` (def.) y `gemini-3.8-flash-lite-tts`.

**Formato de salida:** MP3 mono 44,1 kHz ≈ 129 kbps [MEDIDO en `outputs/tts_00*.mp3`].
Un audio de 5 min pesa ≈ 4,8 MB.

**API key:** se lee de `.env` (`GEMINI_API_KEY`) o se asigna en memoria con `POST /api/key`.
El adaptador **no necesita la key**: habla con la webapp, que ya la tiene (constitución
P2 v1.1 no restringe su manejo; igual no hay motivo para tocarla). No se leyó `.env`.

**Hallazgos que afectan al diseño**
1. **Límite de 8000 caracteres por petición.** Un guion de 5 min (~700–800 palabras,
   ≈ 4.500–5.500 caracteres) cabe; clases de 15 min **no**: hay que partir el texto en
   fragmentos por frases y unir los audios.
2. **Tope de ≈ 60 s por petición: descartado como alarma.** `tts_005.mp3` (59,7 s) y
   `tts_006.mp3` (59,3 s) eran retazos de guiones, no clases completas (confirmado por el
   usuario 2026-10-14). Sigue sin verificarse el comportamiento con 800 palabras
   (≈ 5.000 caracteres, dentro del límite de 8000): se confirma en la primera generación
   real de una clase completa.
3. **Condición de carrera en nombres:** `next_filename()` calcula `tts_NNN` listando
   la carpeta; dos peticiones simultáneas pueden pisarse. El adaptador **serializa**
   las peticiones a la webapp (una a la vez) y usa el nombre que devuelve `file`.
4. **Etiquetas en el texto:** la webapp admite marcas inline del propio Gemini (p. ej.
   `[short pause]`). Nuestras etiquetas de toma (`[toma:...]`, `[pose:...]`,
   `[escenario:...]`, `[plano:...]`) usan prefijos reservados y se eliminan antes de
   enviar; **las demás marcas entre corchetes se envían tal cual**.
5. **Errores:** la webapp traduce 401/404/429/400/502 a `{"error": "..."}` con el código
   HTTP; el adaptador los convierte en el mensaje de FR-013.
6. **Cuota [SIN VERIFICAR, CRÍTICO]:** foros públicos reportan que los modelos TTS de
   Gemini tienen en el nivel gratuito topes diarios muy bajos (se citan desde 10 hasta
   100 peticiones por día, con informes contradictorios y un caso donde el panel mostraba
   un límite mayor que el aplicado). No hay una cifra oficial confiable. Con 7.632
   clases (≥ 7.632 peticiones, más si hay tope de 60 s), 100 peticiones/día **no
   alcanzan en 68 días**. El usuario debe consultar los límites reales de su proyecto en
   AI Studio (página de *rate limits*) **ya**.
   Fuentes: [foro: 100 RPD en gemini-3.8-flash-tts](https://discuss.ai.google.dev/t/gemini-3-8-flash-tts-api-enforces-100-rpd-despite-ai-studio-showing-10k-rpd/187223),
   [foro: cuota gratuita TTS](https://discuss.ai.google.dev/t/gemini-lies-about-free-tier-quota-limits-sudden-resource-exhausted-blockers-on-tts-models/177531),
   [documentación de límites](https://ai.google.dev/gemini-api/docs/rate-limits.md.txt).

**Decisión (integración):** proveedor `gemini-studio` = cliente HTTP delgado de la webapp
(sin importar su código, sin modificarla). Detalle en `contracts/proveedor-tts.md`.
**Alternativas descartadas:** importar `app.py` como módulo (acopla y duplica la
inicialización del cliente); llamar directamente a la API de Google (duplica la gestión
de key y errores, y rompe "mi webapp como fuente de las voces").

**Plan B de audio si la cuota no alcanza (sin costo):** `edge-tts` (voces neuronales de
Microsoft, gratuito, sin límite diario publicado [SIN VERIFICAR]) para el grueso y
`gemini-studio` para clases destacadas; (Piper, que era la opción offline, se retiró el 2026-10-14 por calidad de voz). Esto no
requiere cambiar la spec: ya soporta los tres proveedores.

## 3. Rhubarb Lip Sync y el español

- Última versión estable encontrada: **1.14.0** (GitHub, DanielSWolf/rhubarb-lip-sync);
  la 1.9.0 introdujo el soporte "básico" para otros idiomas mediante reconocimiento
  fonético [fuente](https://github.com/DanielSWolf/rhubarb-lip-sync/releases). Se fija
  la versión exacta y su checksum en el instalador (P4).
- Reconocedores: `pocketSphinx` (solo inglés) y `phonetic` (independiente del idioma).
  Para español → **`-r phonetic`** (FR-021).
- **`--dialogFile` con `-r phonetic` [SIN VERIFICAR]:** se cree que el texto de apoyo solo
  mejora a `pocketSphinx` y que el reconocedor fonético lo ignora. Si es así, el
  "guion como apoyo" de FR-020 no mejorará el lipsync en español; el guion seguiría
  siendo útil para las etiquetas. **Spike S1** lo comprueba con los audios reales
  (`tts_005.mp3`) y se corrige el texto de FR-020 vía cambio de spec si resulta
  necesario.
- Formas: `--extendedShapes GHX` activa G, H y X (A–F son las básicas).
- Velocidad [SIN VERIFICAR]: se mide en el spike S1 (en la estimación de rendimiento se
  reserva ≈ 20–60 s por clase de 5 min).
- Mitigaciones de precisión: suavizado FR-022 (mín. 2 frames), y los cierres A en M/B/P
  se conservan. Criterio del spike: variedad de visemas y revisión visual con bocas
  placeholder; no se persigue exactitud fonética perfecta.

### Resultados del spike S1 [MEDIDO 2026-10-14, `tts_008.mp3`, 280 s, inglés con ejemplos en español]
Rhubarb 1.14.0, `--extendedShapes GHX`. Rhubarb **solo lee WAV/OGG**, no MP3: el módulo
`audio` convierte antes a WAV 16 kHz mono (≈ 9 MB por clase de 5 min, temporal).

| Configuración | Tiempo | Cues | Visemas < 2 frames | Pausas X ≥ 0,3 s |
|---|---|---|---|---|
| `phonetic` sin diálogo | **7,7 s** | 1.705 | 37,6 % | — |
| `phonetic` + `--dialogFile` | **7,8 s** | 1.698 | 37,5 % | 28 (una cada 10 s) |
| `pocketSphinx` + diálogo | 34,5 s | 1.679 | 39,5 % | 30 (una cada 9,3 s) |
| `pocketSphinx` sin diálogo | 32,7 s | 1.672 | 39,7 % | — |

Conclusiones:
1. **`--dialogFile` con `phonetic` casi no cambia nada** (98,9 % de acuerdo frame a frame con
   y sin diálogo); con `pocketSphinx` tampoco mucho (96,1 %). El guion aporta poco al lipsync
   y sí a las etiquetas. La redacción aprobada de FR-020 ("cuando el reconocedor lo admita")
   cubre este resultado. **R3 cerrado.**
2. **Velocidad:** `phonetic` ≈ 36× tiempo real; **~8 s por clase de 5 min**, irrelevante para
   el presupuesto (además se cachea por hash de audio).
3. **Los dos reconocedores discrepan en 1 de cada 3 frames** (acuerdo 66,7 %). Sin una
   referencia no se puede decir cuál es "más exacto": la comparación definitiva es visual.
   **Decisión provisional:** `phonetic` por defecto (sirve en español, inglés y mezclado,
   que es el caso de A1–A2 y B1–B2, y es 4× más rápido); `pocketSphinx` queda como opción
   de configuración (`reconocedor`) para clases casi totalmente en inglés. En el
   checkpoint del MVP renderizaré el mismo audio con ambos para que elijas a ojo.
4. **El suavizado es imprescindible:** más de **1 de cada 3 visemas dura menos de 2
   frames** (mediana 140 ms ≈ 3,5 frames). FR-022 pasa de detalle a pieza clave.
5. **Hay pausas de sobra para cortar tomas:** una pausa X ≥ 0,3 s cada ≈ 10 s.
6. Habla casi continua: solo ≈ 6 % del tiempo en X.

**Mapeo de formas (para la guía de assets):** A = labios cerrados (P, B, M); B = dientes
juntos, boca algo abierta (K, S, T, EE); C = abierta media (EH, AE); D = muy abierta
(AA); E = redondeada media (AO, ER); F = labios fruncidos (UW, OW, W); G = dientes
superiores sobre el labio inferior (F, V); H = lengua alta, boca abierta (L); X = reposo.

**Mapeo texto → tiempo para etiquetas manuales:** como el reconocedor fonético no
entrega palabras, se ubica la etiqueta por **proporción del texto hablado** (posición de
la etiqueta en caracteres ÷ total, aplicada al tiempo con voz, es decir, excluyendo las
pausas X) y luego se ajusta a la pausa X más cercana (±2 s, FR-054). Es una aproximación
deliberada y suficiente porque el cambio de toma no necesita sincronía palabra a palabra.
**Alternativa descartada:** alineación forzada con Whisper/aeneas/MFA (precisión de
palabra, pero cientos de horas de cómputo extra a esta escala y más dependencias, P8).

## 4. Segmentación del personaje (FR-080) [SIN VERIFICAR, spike S2]

| Opción | Pros | Contras |
|---|---|---|
| `rembg` + **BiRefNet** (`birefnet-general`) | Mejor calidad en bordes finos (pelo, monturas de lentes) | Más lento en CPU; modelo grande |
| `rembg` + `isnet-general-use` | Buen equilibrio | Bordes algo peores |
| `rembg` + `u2net` | Rápido y ligero | Calidad inferior en detalles |

**Decisión provisional:** BiRefNet por defecto, `isnet-general-use` y `u2net` como
alternativas por parámetro. Se ejecuta **una vez por pose** (FR-084), así que el tiempo
en CPU (estimado: del orden de segundos a un par de minutos por imagen 4K) no afecta a
los lotes. El spike S2 compara los tres sobre la imagen real del profesor (lentes,
libro, mano) con la métrica IoU contra una máscara corregida a mano, y fija el umbral
de FR-080. Si hay buena GPU sin CUDA instalado, `onnxruntime-directml` es una vía a
evaluar; por defecto CPU (P8).
**Corrección manual:** la máscara se exporta a `mascara.png` (editable en cualquier
editor) y se reimporta (FR-082).

### Resultados del spike S2 [MEDIDO 2026-10-14, `P1_profesor.png` 2048x1152]
| Modelo | Tiempo (CPU) | Calidad |
|---|---|---|
| `u2net` (168 MB) | rápido | Halo claro alrededor del personaje y huecos en el marcador |
| `isnet-general-use` (170 MB) | rápido | Huecos semitransparentes en los lentes y el marcador |
| **`birefnet-general` (928 MB)** | **13 s (+25 s de carga)** | **Limpio: lentes, pelo y marcador sin huecos** |

IoU entre modelos: u2net-isnet 0,963; u2net-birefnet 0,962; isnet-birefnet 0,996. Decisión:
**BiRefNet por defecto** (`MODELO_DEFECTO`). La máscara de referencia revisada a ojo se guardó en
`pruebas/datos/p1_mascara_referencia.png`; FR-080 exige IoU >= 0,95 frente a ella. Se descartaron y
borraron u2net e isnet del proyecto.

## 5. Inpainting (FR-081)

Con el modelo estudio, el inpainting ya **no es necesario para que la respiración no
deje huecos** (el escenario es un fondo limpio independiente). Solo sirve para convertir
el fondo de la imagen original en un escenario. Por eso es opcional y su dependencia
pesada (PyTorch) va en un grupo de instalación separado.

| Opción | Veredicto |
|---|---|
| **LaMa** (`simple-lama-inpainting`) | Elegida: buena en áreas grandes, corre en CPU, modelo de ≈ 200 MB. |
| IOPaint | Más completa pero trae interfaz y dependencias que no se necesitan. |
| `cv2.inpaint` (Telea/NS) | Respaldo sin dependencias pesadas; mala calidad en zonas grandes. |

### Resultados del spike S2 para inpainting [MEDIDO]
| Opción | Tiempo | Calidad |
|---|---|---|
| `cv2.inpaint` (Telea) | 1,2 s | Manchas y bordes visibles donde estaba el personaje |
| **LaMa** (`big-lama.pt`, 196 MB) | **16 s en CPU** | **Fondo limpio y creíble** |

Dos hallazgos: (1) `simple-lama-inpainting` obliga a Pillow 9.5 y numpy 1.26 en el entorno
principal, por eso la preparación vive en `.venv-prep` aislado (1,2 GB); (2) el modelo TorchScript trae
constantes CUDA y falla en CPU con `torch.jit.load` por defecto: hay que cargarlo con
`map_location="cpu"` (lo hace `src/prep/_trabajador.py`). Decisión: **LaMa**. **R4 cerrado.**

## 6. Compositor y codificación [MEDIDO, sintético]

Medición con assets sintéticos a 1280×720 (fondo, cuerpo con escala de respiración por
frame y boca), 1 núcleo, mediana de 3 repeticiones:

| Compositor | ms/frame | fps (1 núcleo) |
|---|---|---|
| **Pillow** (`resize` + `paste` con máscara) | **11,05** | **90,5** |
| OpenCV + mezcla alfa con numpy | 20,21 | 49,5 |

Codificación (solo ffmpeg, fuente sintética, 1.500 frames): **`libx264 -preset veryfast
-crf 23` → ≈ 639 fps** en el equipo. `h264_nvenc` falla por el driver (§1).

**Decisiones**
- **Pillow** para el compositor (más rápido en este patrón y sin dependencia de OpenCV).
  Aviso honesto: la mezcla de OpenCV se escribió de forma simple; no se descarta que
  una versión optimizada la iguale, pero no hay motivo para añadir la dependencia (P8).
- **`libx264` en CPU**; sin NVENC. La codificación no es el cuello de botella
  (≈ 639 fps frente a ≈ 90 fps de composición por núcleo).
- **Estimación de rendimiento (sintética):** una clase de 5 min = 7.500 frames ≈ 83 s
  de composición en 1 núcleo + codificación en paralelo. Con 5 trabajadores, el tiempo
  efectivo ronda **20–40 s por clase** → 7.632 clases ≈ **2–3,5 días** de render
  continuo. Los assets reales (cuerpo grande, plano con zoom, desenfoque) serán más
  lentos; el margen frente a la meta de 2 min por clase es amplio. Se verifica con
  NFR-007 en el spike S3 con assets reales.
- **Optimizaciones previstas:** fondo del escenario y plano precalculados una vez por
  toma (con su desenfoque) y guardados en `cache/`; caché pequeña de cuerpos
  reescalados (la respiración se cuantiza en ≈ 20 niveles); flujo de bytes a ffmpeg
  por `stdin` sin archivos intermedios.

### Mediciones reales con tu pose P1 y tu escenario E1 [MEDIDO 2026-10-14, un trabajo, CPU]
| Audio | Tiempo | Pico de RAM (render + ffmpeg) |
|---|---|---|
| 1 min | 23,9 s | 604 MB |
| 5 min | 98,9 s | 719 MB |
| 10 min | 282 s | 720 MB |

La RAM **no crece con la duración** (NFR-001 cumplido: < 2 GB). Un audio de 5 minutos se renderiza en
99 s, muy por debajo del tope de 10 min (NFR-002). Con 4 trabajadores en paralelo el tiempo efectivo
debería rondar 25–40 s por clase; se confirma en US10.

## 7. Escritura atómica del MP4 (FR-033)

ffmpeg escribe en `<nombre>.part.mp4` (misma carpeta, para que el renombrado sea
atómico en el mismo volumen); al terminar con código 0 y pasar `ffprobe` (duración
≈ audio ±1 frame, códec esperado) se hace `os.replace` al nombre final. Si el proceso
muere, queda solo el `.part`, que la cola borra al reanudar (FR-104). `moov atom` al
inicio con `-movflags +faststart` (reproducción en navegador, SC-001).
**Descartado:** escribir directamente al nombre final y borrar si falla (un corte de
energía lo deja corrupto).

## 8. Audio dentro del MP4 (FR-011)

Si el audio entregado es MP3, se copia al MP4 **sin recodificar** (`-c:a copy`); si es
WAV se codifica a AAC 192 kbps. Hay que confirmar en el spike S3 que el MP3 dentro de
MP4 se reproduce en VLC y en Chrome/Edge (SC-001); si falla, se usa AAC 192 kbps sin
filtros para todo.

## 9. Cola de trabajos (FR-100 a FR-107)

**SQLite** (módulo estándar de Python, un archivo, modo WAL): transacciones atómicas para
reclamar trabajos sin que dos trabajadores tomen el mismo; consultas simples para el
progreso. **Descartados:** Celery/Redis (servidores extra, P8), archivos JSON con
bloqueos (frágiles en Windows), `multiprocessing.Queue` solo en memoria (no persiste).
Trabajadores = procesos independientes (`subprocess`), cada uno con su render en
memoria acotada; un *latido* permite reanudar trabajos huérfanos tras un corte.

## 10. Interfaz web (US6)

**Gradio** (sugerido por el usuario): `gr.Image` con evento de selección entrega las
coordenadas del clic (calibración, FR-062); subir archivos y reproductor de video
integrados (FR-064, FR-071). Corre en `127.0.0.1`. La interfaz es prioridad P3 y no
bloquea el MVP.

## 11. Riesgos y preguntas abiertas para el usuario

| # | Riesgo / pregunta | Gravedad | Acción |
|---|---|---|---|
| R1 | Cuota diaria de Gemini TTS insuficiente para 7.632 clases | ~~Alta~~ Mitigado | El usuario aceptó pagar tokens de Gemini (constitución v1.2): con facturación activa la cuota gratuita deja de ser el límite. Falta verificar límites y precio de su cuenta. |
| R2 | Posible tope de ≈ 60 s por audio generado | Alta | El usuario confirma el texto de `tts_005`/`tts_006`; el adaptador parte el texto de todos modos. |
| R3 | `--dialogFile` sin efecto con el reconocedor fonético | ~~Media~~ Cerrado | S1: efecto mínimo; FR-020 ya lo contempla. La elección de reconocedor se decide a ojo en el MVP. |
| R4 | Calidad de segmentación en lentes/libro/mano | ~~Media~~ Cerrado | S2: BiRefNet limpio sobre la imagen real; la corrección manual de máscara (FR-082) sigue disponible. |
| R5 | Coherencia visual de poses/bocas generadas con IA | Media (del usuario) | `contracts/guia-assets.md`. |
| R6 | Plazo: 68 días para todo | Media | MVP primero; audio y assets en paralelo al desarrollo. |
