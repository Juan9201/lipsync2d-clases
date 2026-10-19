# Pendientes del proyecto — análisis del 2026-10-16

Estado: 81 de 108 tareas de `tasks.md` marcadas; el pipeline de una clase funciona de punta a punta (voz, lipsync, 43 poses, parpadeo,
director con cámara virtual). Lo que sigue es lo que **todavía no está conectado, no se ha medido o necesita una decisión**.
Plazo: 20 de diciembre de 2026 (quedan 65 días). Meta: 7.632 clases de 5 min.

## A. Bloqueantes para producir las 7.632 clases
- [x] **El lote no usa lo nuevo.** (HECHO 2026-10-19) `src/lote/trabajadores.py::parametros_de` pasa una sola pose, sin director y con el reconocedor por
  defecto. Un lote hoy rendería la primera pose, plano PL1, sin variedad. Conectar: poses de la clase, `director=True`, reglas y escenario.
- [x] **Idioma por clase (FR-021).** (HECHO 2026-10-19; falta probar un render real en español) No hay columna `idioma` en el manifiesto ni elección automática del reconocedor (inglés →
  `pocketSphinx` con guion; español → `phonetic`). En esta sesión solo se probó audio en inglés (`tts_008.mp3`). Falta un render real en español.
- [ ] **Lote de 20 clases reales (SC-004, T082).** Solo se midieron 4. Hacen falta 20 guiones (y audios o TTS) reales.
- [ ] **TTS a escala.** ≈ 636 h de audio. La cuota diaria gratuita de Gemini TTS nunca se verificó; decidir cuándo pasar a pago, y plan B
  (`edge`). La clave de API vive en la otra webapp (`gemini-tts-studio/.env`): no copiarla a este repo (es público).
- [ ] **Rendimiento (NFR-007/SC-007, T091/T106).** Con director y parpadeo: 240 s por clase con 1 trabajador (0,86× tiempo real); el
  prototipo sin esto midió ≈ 60 s. A ese ritmo: ≈ 21 días continuos con 1 trabajador, ≈ 7–10 con 3. Perfil de 90 s: 56 % esperando al
  decodificador del fondo (ffmpeg con crop + lanczos + desenfoque), 20 % `alpha_composite`, 15 % copias en Python. Optimizable (≈ 2×).
  Falta medir con varios trabajadores (RAM por trabajador, NFR-009).

## B. Decisiones tuyas
- [ ] **Cejas en el parpadeo.** Recuadro ancho = las cejas saltan en poses con ceño; recuadro «solo lentes» = leve fantasma. Elegir en el
  editor («Recuadro solo en los lentes» / «Volver al ancho») o regenerar las imágenes de parpadeo con las cejas de la pose.
- [ ] **Lentes 3/4.** El cristal de un lente cambia de tono al parpadear en `explicar_01` y `señalar_01` (las imágenes de parpadeo no
  coinciden del todo con la pose). Solo se arregla regenerándolas.
- [ ] **`Frontal_Blink_Middle` sin corrección de color** (el cerrado sí la tiene).
- [ ] **FR-061 relajado** (bocas de distinto tamaño con calibración por forma): propuesto, sin tu OK.
- [ ] **Cejas «amigables» (prompt ya hecho).** Regenerar cabezas obliga a recalibrar y reimportar todo.
- [ ] **Escenarios.** Solo hay uno real (`E2_calle`, video) y un placeholder (`E1_salon`, imagen). Para 7.632 clases, ¿cuántos fondos?
- [ ] **Profesora.** `tts.yaml` tiene voz «mujer», pero no hay personaje femenino. ¿Un solo profesor para todo?
- [ ] **3/4:** una sola variante de reposo por gesto (decidido provisionalmente).
- [x] **Interfaz web (T083–T086).** (HECHO 2026-10-19: `python -m src.ui`; falta subir poses/escenarios) Hoy todo es línea de comandos + las herramientas HTML. ¿Se hace, se recorta o se pospone?

## C. Código y spec incompletos
- [ ] Etiquetas manuales en el guion: T061–T064 (y la prioridad sobre el director, FR-091, que deja T068/T071 a medias).
- [ ] Gestos por palabras clave (español e inglés): T103–T104, `gestos.yaml`. Hoy el acento se elige al azar con semilla.
- [ ] Previsualización de 5 s (`--previa`, T074) y calibración por clic (T072–T073, T105): la calibración ya vive en el Editor de poses
  (HTML); reescribir esas tareas o darlas por cubiertas.
- [ ] `tasks.md` desactualizado: T065–T067 están hechas en la práctica (planos, tomas) pero sin marcar; T091/T092 aparecen dos veces
  (Fase 11 y Fase 12); T082 con anotación suelta.
- [ ] Pulido: T087–T092 (spike con assets reales, suite en ruta con acentos, casos borde, `quickstart.md` desde cero, `validation.md`).
- [ ] Documentación: no hay `README.md` en la raíz; `quickstart.md` sigue como borrador y no menciona `importar-poses`, el Editor de
  poses, `reglas_director.yaml` ni `--director`. FR-065 (README de assets) sin entregar.

## D. Riesgos y orden
- [ ] **Respaldo:** poses, parpadeos, videos y fondos solo existen en esta PC (el repo no los versiona). Los zips de `respaldo_drive/`
  (01–06) hay que subirlos a Drive a mano; confirmar que ya está.
- [ ] **Repo público:** sin claves, pero scripts de `prototipos/` llevan rutas con tu nombre de usuario de Windows.
- [ ] Orden sugerido: (1) conectar lote + idioma, (2) 20 clases reales de punta a punta (mide TTS, tiempo y RAM), (3) optimizar render,
  (4) etiquetas y gestos por palabras clave, (5) pulido y documentación.
