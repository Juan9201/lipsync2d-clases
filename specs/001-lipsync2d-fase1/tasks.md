# Tareas (tasks.md): Lipsync 2D, Fase 1

**Spec:** v3 (aprobada 2026-10-15) + CP-1 a CP-4 · **Plan:** `plan.md` · **Estado:** borrador para aprobación

Formato: `T### [P] [US#] Descripción — archivo(s) — FR/NFR`. `[P]` = paralelizable con otras
tareas de la misma fase (archivos distintos, sin dependencia). Marcar `[x]` al terminar.
**Regla de cada tarea (Definición de Terminado):** tests escritos antes del código y en
verde; requisitos verificados; comentarios en español; sin violar la constitución; yo te
indico cómo probarlo a mano en una o dos líneas.

**Alcance del MVP (SC-001):** Fases 1 a 4 (Setup, Fundacional, US8, US1, US2) con bocas
placeholder. En la fase US8 se implementa **primero el modo de respaldo (FR-083)** y
después la separación completa (FR-080 a FR-082). **No se avanza a US3 hasta que
confirmes el checkpoint del MVP.**

---

## Fase 1: Setup

- [x] T001 Crear la estructura del repositorio (`src/`, `pruebas/`, `herramientas/`, `modelos/`, `entrada/`, `clases/`, `salidas/`, `cache/`, `logs/`, `lote/`), `pytest.ini` y `.gitignore` — `pruebas/`, `src/__init__.py` — FR-001, NFR-005
- [x] T002 [P] Fijar dependencias del núcleo y del grupo de preparación — `requirements.lock`, `requirements-prep.lock` — FR-001
- [x] T003 [P] Fixture de pytest que crea un proyecto temporal en una ruta con espacios y acentos — `pruebas/conftest.py` — NFR-005
- [x] T004 [P] Módulo `registro`: logs por etapa con tiempos y archivo por trabajo (tests primero) — `src/registro.py`, `pruebas/unitarias/test_registro.py` — NFR-006
- [x] T005 [P] Excepciones base con `causa` y `sugerencia` en español (tests primero) — `src/errores.py`, `pruebas/unitarias/test_errores.py` — NFR-006
- [x] T006 Tests de la verificación de entorno (dependencia presente/ausente → mensaje y acción) — `pruebas/unitarias/test_entorno.py` — FR-002
- [x] T007 `src/entorno.py` y `verificar.ps1`: estado de cada dependencia y cómo corregirla — `src/entorno.py`, `verificar.ps1` — FR-002
- [x] T008 `instalar.ps1`: crea `.venv`, instala los locks, descarga ffmpeg y Rhubarb y verifica SHA-256 (`herramientas/checksums.txt`); opción `-Preparacion` para rembg/LaMa — `instalar.ps1` — FR-001, P4
- [x] T009 Publicar el README de assets a partir de `contracts/guia-assets.md` y mostrar su ruta al usuario — `assets/README.md` — FR-065

**Checkpoint 1:** en una carpeta limpia, `instalar.ps1` y `verificar.ps1` terminan en OK (prueba manual).

## Fase 2: Fundacional (bloquea todo lo demás)

### Tests y modelos
- [x] T010 [P] Tests del modelo de pose/escenario y de la carga de `config.yaml` (anclas, espejo, `bocas_de`, planos) — `pruebas/unitarias/test_biblioteca_config.py` — FR-050, FR-051, FR-052
- [x] T011 [P] Tests de validación de assets (bocas faltantes, sin alfa, tamaños distintos, nombres inválidos) — `pruebas/unitarias/test_validacion_assets.py` — FR-061
- [x] T012 [P] Tests de la línea de tiempo (invariantes del contrato: cobertura, visemas ≥ 2 frames salvo A, tomas ordenadas) — `pruebas/unitarias/test_timeline.py` — FR-022, NFR-004
- [x] T013 [P] Tests del codificador (frames por `stdin`, `.part` → renombrado atómico, ffprobe de validación, proceso interrumpido) — `pruebas/unitarias/test_encoder.py` — FR-031, FR-032, FR-033
- [x] T014 [P] Tests del compositor con una capa falsa (no depende de clases concretas) y un frame sintético esperado — `pruebas/unitarias/test_compositor.py` — FR-030, P7
- [x] T015 [P] Tests del módulo `audio` (MP3/WAV, duración, frecuencias de muestreo distintas, archivo corrupto) — `pruebas/unitarias/test_audio.py` — FR-011

### Implementación
- [x] T016 [P] `src/biblioteca/modelos.py` y carga de `config.yaml` de pose y escenario — `src/biblioteca/` — FR-050, FR-052
- [x] T017 [P] `src/biblioteca/validacion.py` (FR-061) con mensajes accionables — `src/biblioteca/validacion.py` — FR-061, NFR-006
- [x] T018 [P] Generador de bocas placeholder por código (A–H, X) y ojos cerrados placeholder — `src/biblioteca/placeholders.py` — FR-060
- [x] T019 [P] `src/timeline.py` (dataclasses, validación, serialización JSON) — `src/timeline.py` — FR-022, NFR-004
- [x] T020 [P] `src/encoder.py` (ffmpeg `libx264` + `stdin`, `.part`, ffprobe, `os.replace`) — `src/encoder.py` — FR-031, FR-032, FR-033
- [x] T021 [P] `src/layers/base.py` (`BaseLayer`, `ProveedorAnclas`) y `src/compositor.py` — `src/layers/base.py`, `src/compositor.py` — FR-030, P7
- [x] T022 [P] `src/audio.py` (validación, duración, remuestreo para análisis) — `src/audio.py` — FR-011

### Spikes y lipsync
- [x] T023 **Spike S1 (hecho, ver research.md):** probar Rhubarb `-r phonetic --extendedShapes GHX` con `tts_005.mp3` y otros audios: variedad de visemas, efecto de `--dialogFile`, tiempo por minuto de audio; registrar en `research.md` y proponer ajuste a FR-020 si procede — `research.md` — FR-020, FR-021
- [x] T024 Tests del módulo `lipsync` (parseo de la salida de Rhubarb, suavizado de visemas, caché por hash, binario ausente) — `pruebas/unitarias/test_lipsync.py` — FR-020, FR-021, FR-022, NFR-006
- [x] T025 `src/lipsync.py` (ejecución de Rhubarb sin shell, caché en `cache/`, suavizado de 2 frames con excepción A en M/B/P) — `src/lipsync.py` — FR-020, FR-021, FR-022

**Checkpoint 2:** las pruebas unitarias del fundacional están en verde y un frame sintético se codifica a un MP4 válido (prueba manual con VLC).

## Fase 3: US8 (P1) — preparar assets desde una imagen única

### Modo de respaldo primero (desbloquea el Hito 1)
- [x] T026 [US8] Tests del modo de respaldo: imagen completa como capa base, boca y ojos animados, parpadeo, sin respiración ni movimiento — `pruebas/unitarias/test_respaldo.py` — FR-083
- [x] T027 [P] [US8] Tests de imagen no 16:9 / baja resolución (aviso, recortar/rellenar sin deformar) — `pruebas/unitarias/test_formato_imagen.py` — FR-085
- [x] T028 [US8] `src/prep/respaldo.py`: crea una pose de respaldo desde la imagen única — `src/prep/respaldo.py` — FR-083, FR-084
- [x] T029 [US8] `src/prep/formato.py`: ajuste a 16:9 (recortar o rellenar) y avisos — `src/prep/formato.py` — FR-085
- [x] T030 [US8] Importador de `entrada/` (clasifica por nombre, valida, ordena en carpetas) y comando `python -m src.biblioteca importar` — `src/biblioteca/importador.py` — FR-064, FR-061

### Separación completa
- [x] T031 [US8] **Spike S2:** comparar BiRefNet, isnet y u2net, y LaMa frente a `cv2.inpaint`, con la imagen única real (requiere la imagen del profesor); fijar modelo por defecto y umbral IoU — `research.md` — FR-080, FR-081
- [x] T032 [P] [US8] Tests de segmentación (máscara conocida, IoU ≥ umbral, transparencia) y de exportar/reimportar máscara — `pruebas/unitarias/test_segmentacion.py` — FR-080, FR-082
- [x] T033 [US8] `src/prep/segmentar.py` (rembg, `mascara.png` editable, `cuerpo.png`) y reimportación de máscara — `src/prep/segmentar.py` — FR-080, FR-082
- [x] T034 [P] [US8] Tests del inpainting: el escenario no tiene píxeles transparentes en la zona del personaje — `pruebas/unitarias/test_inpainting.py` — FR-081
- [x] T035 [US8] `src/prep/inpainting.py` (LaMa; respaldo `cv2.inpaint`) para generar un escenario desde la imagen original — `src/prep/inpainting.py` — FR-081
- [x] T036 [US8] CLI `python -m src.prep pose|escenario` con caché: no repite el proceso si ya existen los resultados — `src/prep/__main__.py` — FR-084

**Checkpoint 3 (US8):** `python -m src.prep pose P1 --respaldo` sobre tu imagen única genera la pose y, con `-Preparacion`, `cuerpo.png` y `mascara.png`; revisa la máscara en un editor (prueba manual).

## Fase 4: US1 (P1) — video desde audio propio y US2 (P1) — audio desde el guion

### US1
- [x] T037 [US1] Test de integración: render de 10 s con bocas placeholder; `ffprobe` valida H.264, yuv420p, 25 fps, 16:9, 1280×720 y audio; MP3 copiado sin recodificar — `pruebas/integracion/test_render_basico.py` — FR-011, FR-031
- [x] T038 [P] [US1] Tests de las capas concretas (fondo con plano PL1, cuerpo, ojos, boca por visema) — `pruebas/unitarias/test_capas.py` — FR-030
- [x] T039 [P] [US1] Tests de CLI (argumentos válidos e inválidos con mensajes en español, guion opcional) — `pruebas/unitarias/test_cli.py` — FR-070, NFR-006
- [x] T040 [US1] `src/layers/` concretas: `FondoLayer`, `CuerpoLayer`, `OjosLayer`, `BocaLayer`, `AnclasEstaticas` — `src/layers/` — FR-030
- [x] T041 [US1] `src/render.py` (orquestador de un trabajo) y `src/cli.py` (`python -m src.render`), con tiempos por etapa — `src/render.py`, `src/cli.py` — FR-070, FR-031, NFR-006
- [x] T042 [P] [US1] Tests y medición de sincronía (desfase visema esperado vs mostrado ≤ 40 ms) — `pruebas/integracion/test_sincronia.py` — NFR-003
- [x] T043 [P] [US1] Mediciones de RAM (audios de 1 y 10 min, pico < 2 GB y sin crecimiento) — `pruebas/medicion/medir_ram.py` — NFR-001
- [x] T044 [P] [US1] Test de determinismo (mismos hashes de frames con la misma semilla) — `pruebas/integracion/test_determinismo.py` — NFR-004
- [x] T045 [P] [US1] Tests de casos borde de audio (silencio largo al inicio o final, MP3 con otra frecuencia, > 10 min, guion vacío o ausente) — `pruebas/integracion/test_casos_borde_audio.py` — NFR-006, FR-011
- [x] T046 [US1] Test de interrupción: matar el render a mitad no deja MP4 con el nombre final — `pruebas/integracion/test_interrupcion.py` — FR-033
- [x] T047 [US1] Medición de rendimiento individual (5 min a 1280×720 en CPU, un trabajo ≤ 10 min) — `pruebas/medicion/medir_tiempo.py` — NFR-002

### US2
- [x] T048 [P] [US2] Tests de contrato del proveedor TTS con servidor HTTP falso de `gemini-studio` (éxito, 429, sin key, webapp apagada) — `pruebas/unitarias/test_tts_gemini.py` — FR-010, FR-013
- [x] T049 [P] [US2] Tests de limpieza de etiquetas (conserva `[short pause]`), partición por frases, reintentos con espera, unión de audios — `pruebas/unitarias/test_tts_comun.py` — FR-012, FR-010
- [x] T050 [US2] `src/tts/` común (limpieza, partición, reintentos, unión) y `ProveedorTTS` — `src/tts/comun.py`, `src/tts/base.py` — FR-012, FR-010, FR-013
- [x] T051 [US2] Proveedor `gemini-studio` (HTTP, peticiones serializadas, mensajes de error en español) — `src/tts/gemini_studio.py` — FR-010, FR-013
- [x] T052 [P] [US2] Proveedor `edge` — `src/tts/edge.py` — FR-010
- [x] T053 [P] [US2] ~~Proveedor `piper`~~ **Retirado el 2026-10-14** por calidad de voz (constitución v1.2); se sustituye por la opción de género — `src/tts/__init__.py`, `tts.yaml` — FR-015
- [x] T054 [US2] Integración en `render`: sin `--audio` genera con `--tts` (defecto `gemini-studio`); si falla, se detiene con causa y alternativas — `src/render.py` — FR-010, FR-013
- [x] T055 [P] [US2] Tests del comando de audios en lote (3 guiones, fallo en la 2.ª petición, reanudable) — `pruebas/unitarias/test_tts_lote.py` — FR-014
- [x] T056 [US2] `python -m src.tts lote --carpeta clases --proveedor …` — `src/tts/lote.py` — FR-014
- [x] T057 [US2] **Spike S4 (hecho):** el usuario eligió la voz `es-419-podcaster-3` de Gemini; edge queda con `en-US-AndrewMultilingualNeural` — `research.md` — FR-010

**Checkpoint 4 / MVP (SC-001):** con tu imagen única en modo de respaldo y bocas placeholder, genera un video de 10 s y ábrelo en VLC y en el navegador (`python -m src.render --guion … --audio … --personaje …`). **Detente aquí hasta tu confirmación.**

---

## Fase 5: US3 (P2) — animación secundaria
- [x] T058 [P] [US3] Tests de parpadeos (intervalos 2–6 s, 3–5 frames, semilla), respiración (±0.5 %, continua) y movimiento leve (solo al hablar, sin saltos) — `pruebas/unitarias/test_animation.py` — FR-040, FR-041, FR-042
- [x] T059 [US3] `src/animation.py` (parpadeos, respiración, movimiento, `hablando`) — `src/animation.py` — FR-040, FR-041, FR-042
- [x] T060 [US3] Integrar la animación en capas y compositor; repetir el test de determinismo (respiración y movimiento quedan apagados por defecto por decisión del usuario; el parpadeo se mantiene) — `src/layers/`, `src/compositor.py` — FR-041, FR-042, NFR-004
- **Checkpoint US3:** mira un video de 30 s: parpadea, respira y se mueve levemente al hablar.

## Fase 6: US4 (P2) — poses, escenarios, planos y etiquetas
> **En pausa por petición del usuario (2026-10-14)** mientras produce la biblioteca de assets con las medidas de `contracts/guia-assets.md`. Se retoma cuando entregue el kit mínimo.
- [ ] T061 [P] [US4] Tests del parser de etiquetas (formas, parciales, errores con línea y columna, prefijos con errata) — `pruebas/unitarias/test_etiquetas.py` — FR-054, FR-055, FR-056
- [ ] T062 [P] [US4] Tests de planos PL1–PL6 (ventana de recorte, desenfoque, aviso de resolución insuficiente) y espejo — `pruebas/unitarias/test_planos.py` — FR-053, FR-051
- [ ] T063 [P] [US4] Tests de restricciones de escenario (planos y poses permitidos) — `pruebas/unitarias/test_restricciones_escenario.py` — FR-052
- [ ] T064 [US4] `src/etiquetas.py` (parser, mapeo texto → tiempo por proporción, ajuste a la pausa X dentro de ±2 s o límite de frase con aviso) — `src/etiquetas.py` — FR-054, FR-055, FR-056
- [ ] T065 [US4] Biblioteca multi-pose y multi-escenario, espejo, `bocas_de`, validación previa de etiquetas antes del primer frame — `src/biblioteca/` — FR-050, FR-051, FR-052, FR-056
- [ ] T066 [US4] Plano como cámara virtual con fondo precalculado en `cache/` — `src/layers/camara.py` — FR-053
- [ ] T067 [US4] Integrar tomas en la línea de tiempo y el compositor (corte directo) — `src/timeline.py`, `src/compositor.py` — FR-054, FR-030
- **Checkpoint US4:** con 2 poses y 2 escenarios, un guion con `[toma:…]` cambia en una pausa cercana; una etiqueta mal escrita falla antes de renderizar.

## Fase 7: US9 (P2) — director automático
- [ ] T068 [P] [US9] Tests del director (duración mínima, no repetir pose, paso de plano, variedad, restricciones de escenario, prioridad de etiquetas, misma semilla = mismas tomas) — `pruebas/unitarias/test_director.py` — FR-090, FR-091, FR-092, FR-093 **(parcial 2026-10-16: hecho sin etiquetas; falta la prioridad de etiquetas manuales, T061–T064)**
- [x] T069 [P] [US9] Test de `reglas_director.yaml` (cambiar un valor cambia el comportamiento) — `pruebas/unitarias/test_reglas_director.py` — FR-094
- [x] T070 [US9] `src/director.py` y `reglas_director.yaml` con valores por defecto — `src/director.py` — FR-090–FR-094
- [ ] T071 [US9] Integrar el director en `render` (completa lo que las etiquetas no fijan) — `src/render.py` — FR-090, FR-091 **(parcial 2026-10-16: hecho sin etiquetas; falta la prioridad de etiquetas manuales, T061–T064)**
- **Checkpoint US9:** un guion sin etiquetas produce un video con tomas variadas y reproducibles con `--seed`.

## Fase 8: US5 (P2) — calibración y previsualización
- [ ] T072 [P] [US5] Tests de guardado de anclas por clic y de la previsualización de 5 s (±1 frame) — `pruebas/unitarias/test_calibracion.py` — FR-062, FR-063
- [ ] T073 [US5] `src/calibracion.py` (coordenadas de clic → `config.yaml`) — `src/calibracion.py` — FR-062
- [ ] T074 [US5] `--previa` (5 s) en `render` — `src/render.py` — FR-063
- **Checkpoint US5:** calibra la boca con clics y mira la previsualización.

## Fase 9: US10 (P2) — producción en lote
- [x] T075 [P] [US10] Tests de la cola SQLite (persistencia, reclamo atómico entre procesos, estados, latido) — `pruebas/unitarias/test_cola.py` — FR-100, FR-102
- [x] T076 [P] [US10] Tests del manifiesto (20 clases, errores por fila, duplicados, archivos inexistentes) y del comando que lo crea desde `clases/` — `pruebas/unitarias/test_manifiesto.py` — FR-101, FR-066
- [x] T077 [P] [US10] Tests de robustez (fallo aislado, reanudación tras matar el proceso, disco bajo, semilla derivada del id) — `pruebas/integracion/test_lote.py` — FR-103, FR-104, FR-106, FR-107
- [x] T078 [US10] `src/lote/cola.py` (SQLite WAL, estados, latido) — `src/lote/cola.py` — FR-100, FR-104
- [x] T079 [US10] `src/lote/manifiesto.py` y `python -m src.lote crear|encolar` — `src/lote/manifiesto.py` — FR-101, FR-066
- [x] T080 [US10] `src/lote/trabajadores.py` (N procesos, reintentos, protección de disco, limpieza de `.part`) y `correr` — `src/lote/trabajadores.py` — FR-102, FR-103, FR-106
- [x] T081 [US10] `python -m src.lote estado` (progreso, tiempos, errores, estimación) — `src/lote/estado.py` — FR-105
- [ ] T082 (medido con 4 clases de 5 min: 180 s en total, 45 s efectivos por clase; falta el lote de 20) [P] [US10] Medición de un lote de 20 clases de 5 min (tiempo efectivo medio, RAM total, tamaño medio del MP4) — `pruebas/medicion/medir_lote.py` — NFR-007, NFR-008, NFR-009
- **Checkpoint US10 (SC-004):** un lote de 20 clases con un guion defectuoso termina 19 y reporta el fallo; apaga la PC a la mitad y reanuda.

## Fase 10: US6 (P3) — interfaz web local
- [x] T083 [P] [US6] Tests de la lógica de la UI (subida y validación de assets, formulario → parámetros de render) — `pruebas/unitarias/test_ui_logica.py` — FR-064, FR-071
- [x] T084 [US6] `src/ui/` con Gradio: pestaña Render (guion, voz o audio, personaje, escenario, resolución, reproductor, descarga) — `src/ui/render.py` — FR-071
- [ ] T085 [US6] Pestaña Biblioteca con arrastrar y soltar y selector de archivos, validación al subir, y pestaña Calibración por clic — `src/ui/biblioteca.py`, `src/ui/calibracion.py` — FR-064, FR-062 **(parcial 2026-10-19: guiones, voces, render, lote y subida de escenarios/fondos hechos; falta subir poses y la calibración, que sigue en el Editor de poses)**
- [x] T086 [US6] Pestaña Cola/Lotes (estado en vivo) — `src/ui/lotes.py` — FR-105
- **Checkpoint US6:** sube una pose arrastrándola, renderiza y descarga el MP4 desde el navegador.

## Fase 11: Pulido y validación
- [ ] T087 [P] Spike S3 con assets reales: ajustar planos, desenfoque y tamaños de boca; confirmar MP3 en MP4 en VLC y Chrome — `contracts/config-pose-escenario.md`, `research.md` — FR-053, FR-011
- [ ] T088 [P] Suite completa sobre una ruta con espacios y acentos — `pruebas/` — NFR-005
- [ ] T089 [P] Revisar que todos los casos borde de la spec produzcan mensajes en español con una acción — `pruebas/integracion/test_casos_borde.py` — NFR-006
- [ ] T090 Validar `quickstart.md` desde cero con un usuario nuevo — `quickstart.md` — SC-003
- [ ] T091 Medición de 500 clases (o proyección con un lote de 20) frente a SC-005 y SC-006; ajustar trabajadores — `pruebas/medicion/` — SC-005, SC-006
- [ ] T092 Redactar `validation.md`: matriz FR/NFR → tests → resultado, y evidencia de los SC (comando, duración, RAM, archivo) — `specs/001-lipsync2d-fase1/validation.md` — todos

---

## Dependencias entre fases
Setup → Fundacional → US8 → US1 y US2 (US2 es independiente de US1 salvo T054) →
**checkpoint del MVP** → US3 → US4 → US9 → US5 → US10 → US6 → Pulido. US5, US9 y US10 pueden
reordenarse si lo pides; US10 conviene antes de la producción masiva.

## Fase 12: Spec v3 — fondo en video, vistas 3/4, calibración por forma y naturalidad
> Añadida el 2026-10-15 tras aprobar la spec v3. Los prototipos que validaron estas ideas están en `Temp Real Assest Testing/` (calibradores HTML, render de prueba con fondo en video, 43 poses y sus parpadeos). **Cada tarea sigue la Definición de Terminado: tests primero.** La Fase 6 (poses y etiquetas), en pausa hasta el kit de assets, ya puede retomarse: el usuario entregó 43 poses, 9 bocas por vista y los parpadeos.
- [x] T091 [P] [US11] Tests del fondo en video: bucle con fundido de empalme (sin salto en la unión), lectura en streaming con RAM constante, plano sobre el video, video corto, otra resolución o fps — `pruebas/unitarias/test_fondo_video.py` — FR-057, FR-058
- [x] T092 [US11] `src/layers/fondo_video.py` (`VideoLoopLayer(BaseLayer)`: bucle con fundido de 1 s, un frame cada vez por ffmpeg, a 25 fps) y su integración con el plano — `src/layers/fondo_video.py`, `src/layers/camara.py` — FR-057, FR-058
- [x] T093 [P] [US12] Tests de la biblioteca de poses por vista y gesto (`<vista>_<gesto>_<NN>`), juego de bocas por vista, reflejo de pose y reflejo por forma (`m`, con anulación al combinarse) — `pruebas/unitarias/test_poses_vistas.py` — FR-050, FR-051, FR-067
- [x] T094 [US12] Modelo y validador de `config.yaml` v4 por pose: por forma `x, y, s, r, m`; `vista`, `gesto`, `tipo`, `variante`, `espejo`, `parpadeo` — `src/biblioteca/config_pose.py`, `src/biblioteca/validacion.py` — FR-050, FR-051, FR-062, FR-061
- [x] T095 [US12] Importador de calibraciones: leer el JSON v4 que exportan los calibradores (`poses` o una sola pose) y guardarlo en el `config.yaml` de cada pose; pasar las 11 poses 3/4 ya calibradas (`Calibrador4/calibraciones_34_todas_v3.json`) — `src/biblioteca/importador.py` — FR-062, FR-067
- [x] T096 [US12] Compositor: bocas por forma (posición, escala, giro y reflejo propios), vista y reflejo según la pose — `src/compositor.py`, `src/layers/concretas.py` — FR-030, FR-051, FR-062
- [x] T097 [P] [US12] Tests de la alineación de cabezas en el corte entre poses (por el pelo, con las bocas desplazadas; el salto medio baja y se puede desactivar) — `pruebas/unitarias/test_alineacion_cabeza.py` — FR-059
- [x] T098 [US12] Alineación de cabezas por el pelo en el cambio de pose — `src/timeline.py`, `src/compositor.py` — FR-059
- [x] T099 [P] [US13] Tests de parpadeo por imagen (solo cambia la zona de los ojos, parpadeo doble con su probabilidad, nunca en un cambio de pose, pose sin parpadeo avisa) — `pruebas/unitarias/test_parpadeo_imagen.py` — FR-040, FR-043
- [x] T100 [US13] Parpadeo por imagen: `<pose>_parpadeo.png` (3/4) y `frontal_parpadeo.png`/`_medio.png` (frontales, con `ojos_de`); pegado acotado a la banda de los lentes por ojo para no mover las cejas — `src/animation.py`, `src/layers/concretas.py` — FR-040, FR-043, FR-049
- [x] T101 [P] [US13] Tests de las variantes de reposo (sin repetir, cambio en pausa con mezcla de 2 frames, semilla) y de los acentos (3–6 s, vuelven al reposo, uno cada 20 s como máximo) — `pruebas/unitarias/test_naturalidad.py` — FR-044, FR-045, FR-046
- [x] T102 [US13] Variantes de reposo y acentos en el director, con todos los valores en `reglas_director.yaml` y cada comportamiento apagable — `src/director.py`, `reglas_director.yaml` — FR-044, FR-045, FR-046
- [ ] T103 [P] [US9] Tests del diccionario de palabras clave por idioma (español e inglés) y de la colocación del gesto en la pausa más cercana (±2 s) con registro del motivo — `pruebas/unitarias/test_gestos_palabras.py` — FR-095, FR-096
- [ ] T104 [US9] Gestos por palabras clave en el director (`gestos.yaml`) — `src/director.py`, `gestos.yaml` — FR-095, FR-096
- [ ] T105 [US5] Llevar a la UI y a `src/calibracion.py` la calibración por forma de los prototipos HTML (arrastrar, lupa, fantasma, traer valores, reflejo por forma, exportar e importar todas las poses) — `src/ui/calibracion.py`, `src/calibracion.py` — FR-062
- [ ] T106 [P] Medición con fondo en video, 3/4, parpadeo y variantes: tiempo efectivo por clase y tamaño del MP4 (prototipo sin parpadeo: ≈60 s y 13–21 MB con un trabajador) — `pruebas/medicion/`, `validation.md` — SC-007, NFR-007, NFR-008
- **Checkpoint v3:** una clase de 5 minutos con el fondo en video de la calle, cortes entre poses frontales y 3/4 (con reflejo), parpadeo, variantes de reposo y un acento por palabra clave; revisa que no haya saltos raros ni gestos repetidos.

## Qué necesita cada tarea de tu parte (assets reales)
| Tarea | ¿Necesita assets reales? |
|---|---|
| T001–T030, T032–T057, T058–T086 | **No.** Se construyen y prueban con assets sintéticos y placeholders. |
| T031 (Spike S2) | **Sí, la imagen única** del profesor (idealmente pronto). |
| T028 / Checkpoint 3 / Checkpoint MVP | La imagen única (modo de respaldo + placeholders). |
| T087 (Spike S3) y SC-002 | Poses, ojos y bocas reales; escenarios reales. |
| T057 (Spike S4) | Una muestra de la voz de referencia (ya tienes `tts_00*.mp3`). |

## Cobertura de requisitos
Todo FR y NFR de la spec aparece en al menos una tarea: FR-001/002 (T001–T008), FR-010–014
(T048–T057), FR-020–022 (T023–T025), FR-030–033 (T013–T014, T020–T021, T037–T046), FR-040–042
(T058–T060), FR-050–056 (T010, T016, T061–T067), FR-060–066 (T009, T011, T017–T018, T030,
T072–T085, T076, T079), FR-070/071 (T039–T041, T083–T084), FR-080–085 (T026–T036), FR-090–094
(T068–T071), **(v3)** FR-043–046 (T099–T102), FR-057/058 (T091–T092), FR-059 (T097–T098), FR-067 (T093–T096), FR-095/096 (T103–T104), FR-100–107 (T075–T081), NFR-001–009 (T042–T047, T082, T088–T089).
