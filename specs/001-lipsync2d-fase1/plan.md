# Plan de implementación (plan.md): Lipsync 2D, Fase 1

**Spec:** `spec.md` v2 (aprobada) · **Constitución:** v1.1 · **Estado:** borrador para aprobación
Decisiones y evidencia: `research.md`. Contratos: `contracts/`.

---

## 1. Resumen técnico

Pipeline local en Python 3.11 que, para cada clase, toma `voz.mp3` (+ guion opcional),
obtiene visemas con Rhubarb (`-r phonetic --extendedShapes GHX`), decide las tomas
(etiquetas + director por reglas), compone cada frame con Pillow y lo envía por `stdin` a
ffmpeg (`libx264`), escribiendo el MP4 de forma atómica. Una cola SQLite reparte clases a
N procesos de render para producir miles de videos. Todo gratis y local; internet solo
para el TTS elegido.

## 2. Pila tecnológica

| Capa | Elección | Versión | Nota |
|---|---|---|---|
| Lenguaje | Python | 3.11.9 (instalado) | venv en `.venv/` del proyecto |
| Imagen | Pillow, numpy | fijadas en `requirements.lock` | compositor (research §6) |
| Video/audio | ffmpeg + ffprobe | build fija, descargada por el instalador | `libx264`; sin NVENC |
| Lipsync | Rhubarb Lip Sync | 1.14.0 (verificar en S1) | binario descargado con checksum |
| TTS | adaptador `gemini-studio`, `edge-tts` | fijadas | contrato `proveedor-tts.md` |
| Preparación (grupo opcional) | rembg (+ onnxruntime), LaMa (`simple-lama-inpainting`, PyTorch) | fijadas | solo para `prep` |
| Cola | `sqlite3` (estándar) | — | modo WAL |
| Config | PyYAML | fijada | `config.yaml`, reglas del director |
| UI | Gradio | fijada | P3 |
| Pruebas | pytest, pytest-cov | fijadas | P6 |

**Instalación (FR-001, P4):** `instalar.ps1` crea `.venv`, instala `requirements.lock`
(dependencias del núcleo) y, aparte, `requirements-prep.lock` (PyTorch, rembg: pesado y
solo para preparar assets). Descarga ffmpeg, Rhubarb y los modelos a
`herramientas/` y `modelos/`, **verificando SHA-256** de cada descarga (guardados en
`herramientas/checksums.txt`). `verificar.ps1` implementa FR-002.

## 3. Arquitectura por módulos (`src/`)

| Módulo | Responsabilidad | Requisitos |
|---|---|---|
| `entorno` | Verificación de dependencias y mensajes correctivos | FR-002 |
| `biblioteca` | Poses y escenarios: carga de `config.yaml`, validación, importador de `entrada/` | FR-050–052, 060, 061, 064 |
| `prep` | Segmentación (rembg), máscara editable, inpainting (LaMa), 16:9, respaldo | FR-080–085 |
| `tts` | Proveedores intercambiables, limpieza de etiquetas, partición, reintentos, lote de audios | FR-010–013 |
| `audio` | Lectura/validación de MP3/WAV, duración, remuestreo para análisis | FR-011, 021 |
| `lipsync` | Ejecuta Rhubarb, caché por hash del audio, suavizado | FR-020–022 |
| `etiquetas` | Parser de etiquetas del guion, errores con línea | FR-012, 054–056 |
| `director` | Elección de tomas por reglas con semilla | FR-090–094 |
| `animation` | Parpadeos, respiración, movimiento leve, `hablando` | FR-040–042 |
| `timeline` | Ensambla y valida la línea de tiempo (contrato) | FR-054, NFR-003/004 |
| `layers` | `BaseLayer` + capas concretas; `ProveedorAnclas` | FR-030, P7 |
| `compositor` | Compone un frame desde la línea de tiempo y las capas | FR-030, 053 |
| `encoder` | Proceso ffmpeg, `stdin`, atómico, ffprobe de validación | FR-031–033 |
| `render` | Orquesta un trabajo de punta a punta; `python -m src.render` | FR-070, NFR-* |
| `lote` | Cola SQLite, trabajadores, reanudación, estado, protección de disco | FR-100–107 |
| `cli` | Argumentos y mensajes en español | FR-070 |
| `ui` | Gradio: render, biblioteca (arrastrar y soltar), calibración, cola | FR-062, 064, 071 |
| `registro` | Logs por etapa con tiempos | P9 |

### Flujo de un trabajo (`render`)
```
entrada(clase) → [TTS si no hay audio] → audio.validar → lipsync (caché) →
etiquetas.parsear → director.completar → animation.generar → timeline.validar →
biblioteca.validar(assets usados) → para cada frame: compositor → encoder(stdin) →
ffprobe → renombrado atómico
```
Cada etapa registra inicio, fin y duración (P9). Cualquier error se convierte en un
mensaje en español con la acción correctiva (NFR-006) y no deja archivos finales.

### Memoria acotada (P3, NFR-001)
Solo se mantienen en memoria: assets de la toma activa (con caché LRU acotada de cuerpos
reescalados) y **un** frame a la vez. El fondo con plano y desenfoque se precalcula una
vez y se guarda en `cache/` como imagen; los trabajadores lo leen.

## 4. Capas y diseño para la Fase 2 (P7)

```python
class BaseLayer(Protocol):
    def renderizar(self, ctx: ContextoFrame) -> CapaRGBA | None: ...
    # ctx: n_frame, t, toma activa, visema, parpadeo, transformación (escala, dx, dy),
    #      tamaño de salida. Devuelve la capa ya posicionada o None.

class ProveedorAnclas(Protocol):
    def anclas(self, n_frame: int, pose: str) -> Anclas: ...   # boca, ojos, cabeza
```
- Hoy: `FondoLayer` (imagen estática del escenario + plano), `CuerpoLayer`,
  `OjosLayer`, `BocaLayer`; `AnclasEstaticas` lee `config.yaml`.
- El `compositor` recibe una **lista ordenada de capas** y un `ProveedorAnclas`; nunca
  importa clases concretas. Test con capa falsa que lo demuestra (constitución P7).
- **Fase 2, `VideoLoopLayer(BaseLayer)`:** lee frames de un video en bucle (decodificación
  por ffmpeg en streaming, un frame cada vez) y reemplaza a `FondoLayer`/`CuerpoLayer` en
  la lista de capas. **`AnclasPorFrame(ProveedorAnclas)`:** lee un archivo
  `anclas.jsonl` (una línea por frame, generado por un tracker) y devuelve boca y ojos de
  ese frame. Ni el compositor ni el encoder cambian; solo se registran dos clases nuevas
  y una opción de configuración.

## 5. Estrategia de pruebas (P6)

| Nivel | Qué | Cómo |
|---|---|---|
| Unitarias | Parser de etiquetas, suavizado de visemas, parpadeos, respiración, director, validación de assets, normalización de nombres | `pytest` con datos sintéticos, sin red |
| Contrato | Línea de tiempo cumple sus invariantes; proveedores TTS cumplen la interfaz | `pytest` con dobles de prueba (servidor HTTP falso para `gemini-studio`) |
| Golden | Frame de prueba = imagen de referencia; hash de frames para NFR-004/FR-107 | Imágenes sintéticas generadas por código |
| Integración | Render completo de 10 s con bocas placeholder; `ffprobe` valida códec, fps, resolución, audio | Ruta con espacios y acentos (NFR-005) |
| Cola | Lote de 20 con un fallo; matar el proceso y reanudar | Procesos reales con audios cortos |
| Medición | RAM (1 y 10 min), tiempo (5 min, lote de 20), tamaño del MP4, desfase de visemas | Scripts en `pruebas/medicion/`, resultados en `validation.md` |
| Manual | VLC y navegador; calibración por clics; subida en la UI | Checkpoints de `tasks.md` |

El **TTS real** (Gemini/edge) se prueba de forma manual; en automático se usan dobles
(constitución P2: la suite pasa sin red).

## 6. Spikes (investigación técnica corta, al inicio de la Fase Fundacional)

| ID | Pregunta | Entrada necesaria | Salida |
|---|---|---|---|
| S1 | ¿Rhubarb fonético sirve en español? ¿`--dialogFile` aporta? ¿Cuánto tarda? | `tts_005.mp3` y otros audios reales | Decisión sobre FR-020, tiempo por clase |
| S2 | ¿Qué modelo de segmentación y qué inpainting dan mejor resultado? | Imagen única real del profesor | Modelo por defecto y umbral IoU de FR-080 |
| S3 | ¿Planos, desenfoque, bocas y tiempos con assets reales? ¿MP3 en MP4 reproduce en VLC/Chrome? | Primeras poses/bocas reales o placeholder | Ajuste de los valores por defecto de planos; confirmar NFR-007 |
| S4 | ¿Qué voz masculina de Gemini? (hecho: `es-419-podcaster-3`) | Muestras de la webapp | Voz por defecto |

## 7. Chequeo de la constitución

| Principio | Cómo lo cumple el plan | Estado |
|---|---|---|
| **P1 Costo cero** | Solo software libre y gratuito; Gemini solo vía la webapp del usuario (cuenta del usuario, gratuita o de pago, excepción de la v1.2); `edge-tts` gratuito | ✅ |
| **P2 Local-first** | Render, prep y cola locales; TTS con internet solo `gemini-studio`/`edge` (v1.2: sin voz offline obligatoria); el render acepta audio propio y la suite de pruebas corre sin red | ✅ |
| **P3 Memoria acotada** | Frames en streaming a ffmpeg; caché LRU acotada; NFR-001/009 medidos | ✅ |
| **P4 Reproducibilidad** | `requirements.lock`, binarios y modelos con SHA-256, `instalar.ps1`, semilla determinista | ✅ |
| **P5 Windows-first** | `pathlib`, listas de argumentos sin shell, PowerShell, sin admin, pruebas con ruta con espacios y acentos | ✅ |
| **P6 Test-first** | Nivel de pruebas por requisito, tests antes del código en cada tarea | ✅ |
| **P7 Modularidad** | `BaseLayer` y `ProveedorAnclas`; diseño de Fase 2 en §4 | ✅ |
| **P8 Simplicidad** | SQLite y `subprocess` en vez de brokers; Pillow en vez de OpenCV; PyTorch aislado en un grupo opcional; sin alineación forzada ni NVENC | ✅ |
| **P9 Observabilidad** | Módulo `registro`; tiempos por etapa; errores accionables en español | ✅ |

**Justificaciones de complejidad (P8):** la cola SQLite y el director se incluyen porque
US9 y US10 los exigen; el `ProveedorAnclas` existe por la Fase 2 (P7) y es una interfaz
de una función.

## 8. Rendimiento y plazo

- Medido (sintético): composición 90 fps por núcleo, codificación ≈ 639 fps (research §6).
- Estimado: 20–40 s efectivos por clase con 5 trabajadores → **2–3,5 días** de render
  para 7.632 clases, muy por debajo de los 45 días reservados. La parte crítica del plazo
  **no es el render**: es el **audio** (cuota de Gemini, riesgo R1/R2) y la **producción
  de assets** del usuario.
- Cronograma orientativo: del 13 al ~30 de octubre MVP (SC-001); noviembre: US3–US5,
  director y lotes (SC-004); resto: producción masiva en paralelo a la generación de
  audios. Los audios pueden generarse **desde ya**, sin esperar al sistema.

## 9. Riesgos (resumen; detalle en research §11)
R1 cuota TTS · R2 posible tope de ≈ 60 s por audio · R3 `--dialogFile` · R4 segmentación ·
R5 coherencia visual de los assets · R6 plazo.

## 10. Cambios propuestos a la spec (**requieren tu aprobación; no se aplican solos**)

| ID | Cambio | Motivo |
|---|---|---|
| **CP-1** | Añadir **FR-014**: el sistema DEBE generar en lote los audios de una carpeta de guiones con el proveedor elegido, reanudable y con reintentos ante límites de cuota, guardando `<id>.mp3` junto a `<id>.txt`. Criterio: con 3 guiones y un doble de prueba que falla la 2.ª vez, se generan los 3 audios tras el reintento; relanzar no regenera los existentes. | El usuario genera los audios por adelantado y a escala; hoy solo hay TTS por clase. |
| **CP-2** | En FR-020, sustituir "usando el guion como apoyo" por "usando el guion como apoyo **cuando el reconocedor lo admita**" (se decide tras el spike S1). | `--dialogFile` podría no tener efecto con el reconocedor fonético. |
| **CP-3** | Añadir **FR-066**: el sistema DEBE ofrecer un comando que cree el manifiesto de lote a partir de una carpeta de guiones y audios (`clases/<id>.txt` + `.mp3`). | Los guiones existen sin organizar; evita armar el CSV a mano. |
| **CP-4** | Precisar FR-011: un MP3 se copia sin recodificar; un WAV se codifica a AAC 192 kbps. | Aclara "sin modificar el audio" (research §8). |

## 11. Estructura de archivos del repositorio (código)
```
src/        (módulos de §3)          pruebas/ unitarias, integracion, medicion
herramientas/ (ffmpeg, rhubarb)   modelos/ (segmentación, LaMa)
instalar.ps1  verificar.ps1  requirements.lock  requirements-prep.lock
specs/        (este documento y la constitución)
```
