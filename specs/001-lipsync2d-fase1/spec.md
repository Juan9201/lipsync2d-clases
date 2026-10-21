# Especificación 001: Lipsync 2D para clases educativas (Fase 1)

**Estado:** v3 APROBADA (2026-10-15). Parte de la v2 aprobada (con sus cambios ya registrados en el changelog) e incorpora lo descubierto con las pruebas reales: fondo en video, vistas 3/4 con reflejo, gestos, calibración por forma y naturalidad. Los requisitos nuevos o modificados de la v3 llevan la marca **(v3)**.
**Constitución aplicable:** `specs/constitution.md` v1.2
**Alcance de este documento:** QUÉ debe hacer el sistema y POR QUÉ. El CÓMO
(arquitectura, bibliotecas, formatos internos) se decide en `plan.md`.

> Nota: algunos nombres propios (Rhubarb, edge-tts, `gemini-studio`) aparecen
> aquí porque son restricciones que el usuario fijó de antemano o parte de la interfaz
> pública (valores de `--tts`). No se interpretan como decisiones de diseño interno.

---

## 1. Problema y meta

Producir videos de clases de 5 a 15 minutos donde un personaje 2D (profesor con
lentes y camisa blanca) hable sincronizado con un audio en español, inglés o mezclado, sobre distintos
escenarios y con variedad de poses y planos fotográficos. Las soluciones probadas
(ComfyUI + Wan 2.1 + LatentSync en un POD; servicios comerciales) son caras, lentas e
inestables. La solución usa animación 2D por visemas (formas de boca dibujadas), sin
IA generativa para la boca.

**Meta de producción (corregida 2026-10-21):** 480 clases con el personaje animado, de 5 minutos (≈ 40 horas de video). Son
las 3 clases «IA» de cada uno de los 160 módulos (4 niveles A1–B2 × 40 módulos); la primera clase de cada módulo la da una
persona y no se renderiza. Las 7.632 «actividades» del curso incluyen además quices y examen en H5P y la clase de conclusión
(Google Vids), que no son de este proyecto. La cifra anterior (7.632 clases, ≈ 636 h) era un malentendido.
Guiones: 640 (160 por nivel, 4 por módulo); se renderizan los subtemas 2.º–4.º de cada módulo.

**Modelo "estudio de animación":** el usuario crea una vez una biblioteca de poses del
personaje y una biblioteca de escenarios; el sistema solo anima, compone y sincroniza
con la voz entregada (`voz.mp3`). Los planos fotográficos son una cámara virtual
sobre la composición, no archivos adicionales. El escenario puede ser una imagen o un video corto en bucle **(v3)**.

## 2. Usuario y equipo de referencia

Creador de contenido educativo con conocimientos técnicos intermedios que trabaja en
Windows. Equipo de referencia: AMD Ryzen 5 5600 (6 núcleos / 12 hilos), 64 GB de RAM,
NVIDIA RTX 3050 de 8 GB, 700 GB libres para salidas. La GPU es opcional: puede
acelerar la preparación de assets y la codificación, pero nada depende de ella.

## 3. Historias de usuario

Cada historia se puede probar por separado.

| ID | Prioridad | Historia |
|---|---|---|
| US1 | P1 (MVP) | Como creador, quiero generar un video a partir de un audio propio (`voz.mp3`), un guion opcional, una pose y un escenario, para obtener una clase con la boca sincronizada. |
| US2 | P1 | Como creador, quiero generar el audio desde el guion con mi voz de Gemini TTS o con una voz gratuita en español, para no preparar el audio aparte. |
| US8 | P1 | Como creador, quiero entregar una imagen única (personaje + fondo unidos) y que el sistema extraiga al personaje como pose y el fondo como escenario, para no separarlos a mano en un editor. |
| US3 | P2 | Como creador, quiero que el personaje parpadee, respire y se mueva levemente al hablar, para que no se vea rígido. |
| US4 | P2 | Como creador, quiero poder cambiar de pose, escenario y plano fotográfico con etiquetas en el guion, para controlar la composición cuando me interese. |
| US9 | P2 | Como creador, quiero que el sistema elija solo las tomas (pose, escenario y plano) con reglas, de forma reproducible, para no dirigir cada clase como un director de cine. |
| US10 | P2 | Como creador, quiero encolar lotes de 20 o más clases (cada una con su audio, guion y semilla) y que se procesen sin intervención, para producir miles de clases. |
| US11 | P2 | **(v3)** Como creador, quiero que el escenario pueda ser un video corto en bucle (calle, exteriores), para que el fondo tenga vida sin repetir un corte brusco. |
| US12 | P2 | **(v3)** Como creador, quiero poses en vista frontal y en 3/4, con gestos distintos y con el reflejo de las bocas para el lado contrario, para variar la composición sin rehacer assets. |
| US13 | P2 | **(v3)** Como creador, quiero que el profesor no se quede quieto en una pose (variantes de reposo, parpadeo variado, gestos de acento que vuelven al reposo), para que la clase se vea humana. |
| US5 | P2 | Como creador, quiero calibrar la posición de la boca y los ojos haciendo clic sobre el personaje, para no editar coordenadas a mano. |
| US6 | P3 | Como creador, quiero una interfaz web local para pegar el guion, elegir voz o audio, pose y escenario, subir assets arrastrando archivos, renderizar y descargar el MP4. |
| US7 | — | *Retirada de la Fase 1* (subtítulos .srt; ver sección 10). |

### Escenarios de aceptación por historia

- **US1:** DADO un audio MP3/WAV, una pose con sus assets y un escenario, CUANDO se
  ejecuta el render, ENTONCES se obtiene un MP4 cuyo audio es el entregado y cuya boca
  cambia de forma en sincronía con él. El guion es opcional; con guion el lipsync
  mejora y se habilitan las etiquetas; sin guion se usa una sola toma y se avisa.
- **US2:** DADO un guion sin audio, CUANDO se elige cada proveedor (`gemini-studio`,
  `edge`), ENTONCES se genera el audio y el video; si el proveedor no está
  disponible, el sistema se detiene explicando la causa y ofreciendo alternativas.
- **US8:** DADA una imagen única 16:9, CUANDO se prepara, ENTONCES se obtiene la pose
  (máscara editable y cuerpo con transparencia) y, opcionalmente, el fondo limpio como
  escenario nuevo.
- **US3:** DADO un video renderizado, ENTONCES hay parpadeos, respiración y movimiento
  leve mientras habla, sin saltos bruscos entre frames consecutivos.
- **US4:** DADO un guion con etiquetas de toma, ENTONCES el cambio ocurre en una pausa
  cercana a la etiqueta; con una etiqueta inexistente, el sistema falla antes de
  renderizar y lista las opciones válidas.
- **US9:** DADO un guion sin etiquetas, ENTONCES el video alterna poses y planos
  siguiendo las reglas, y con la misma semilla el resultado es idéntico.
- **US10:** DADO un lote de 20 clases con un trabajo defectuoso, ENTONCES se completan
  las otras 19, el defectuoso se reporta con su causa, y si se apaga la PC a la mitad,
  al reanudar no se repiten los trabajos terminados.
- **US5:** DADA una pose sin anclas, CUANDO el usuario hace clic en la boca y los ojos,
  ENTONCES las anclas quedan guardadas y el render las usa.
- **US6:** DADA la interfaz web local, CUANDO el usuario completa el formulario y pulsa
  "Render", ENTONCES puede reproducir y descargar el MP4; y puede arrastrar assets que
  quedan validados y guardados en la carpeta correcta.
- **US11 (v3):** DADO un escenario de video de 15 s y una clase de 280 s, ENTONCES el fondo se
  repite sin salto visible en la unión (fundido de empalme) y el personaje queda por delante.
- **US12 (v3):** DADA una pose 3/4 que mira a la derecha y otra reflejada, ENTONCES las nueve
  formas de boca encajan en ambas con su posición, tamaño y giro propios, y la sincronía con la
  voz no cambia al cortar entre poses.
- **US13 (v3):** DADA una clase de 5 minutos, ENTONCES el personaje parpadea con intervalos
  irregulares, alterna variantes de reposo (sin repetir la misma dos veces seguidas) y los gestos
  de acento (pulgar, señalar) duran pocos segundos y regresan al reposo.

## 4. Conceptos y nomenclatura

| Concepto | Código | Descripción |
|---|---|---|
| Pose **(v3)** | `<vista>_<gesto>_<NN>` | El personaje recortado (alta resolución) con su vista, su gesto, su variante, su calibración de bocas y, si existe, su imagen de ojos cerrados. Ejemplos: `frontal_neutro_01`, `tres_cuartos_der_explicar_01`. Poses con otro ángulo de cámara (p. ej. contrapicado) son poses distintas. |
| Vista **(v3)** | `frontal`, `tres_cuartos_der` | Orientación de la cabeza y el cuerpo. Una cabeza 3/4 que mira a la izquierda usa las mismas imágenes de bocas reflejadas. |
| Gesto **(v3)** | `neutro`, `explicar`, `pulgar`, `señalar`, `bienvenida`, `pregunta`, `contar`, `libreta` | Acción del torso. Tipo *estado* (puede mantenerse mucho tiempo) o *acento* (breve; vuelve solo al reposo). |
| Variante **(v3)** | `01`, `02`… | Versiones del mismo gesto con pequeñas diferencias; se alternan para evitar la inmovilidad. |
| Juego de bocas **(v3)** | por vista | Las nueve formas A–H y X de una vista. Cada pose guarda la posición, tamaño, giro y reflejo de cada forma. |
| Escenario | `E<n>[_nombre]` | Imagen de fondo 16:9 limpia. Puede declarar qué planos y poses admite. |
| Plano | `PL1`–`PL6` | Cámara virtual sobre la composición: 1 entero, 2 americano, 3 cintura, 4 busto, 5 primer plano, 6 primerísimo primer plano. Códigos fijos. |
| Toma | pose + escenario + plano | Composición activa en un momento del video. |

Ángulo de cámara: en la Fase 1 solo normal. El plano detalle queda fuera.

## 5. Requisitos funcionales (EARS)

### Instalación y entorno
- **FR-001:** El sistema DEBE proveer un instalador para Windows que cree el entorno
  de Python, instale las dependencias y descargue ffmpeg, Rhubarb Lip Sync y los modelos de segmentación e inpainting dentro de la carpeta del
  proyecto.
- **FR-002:** CUANDO el usuario ejecute la verificación del entorno, el sistema DEBE
  informar el estado de cada dependencia y la acción correctiva si alguna falla.

### Audio
- **FR-010:** CUANDO no se entregue un audio, el sistema DEBE generarlo desde el guion
  con el proveedor TTS elegido (`gemini-studio` o `edge`). El proveedor por
  defecto es `gemini-studio`.
- **FR-011:** CUANDO se entregue un audio propio (MP3 o WAV), el sistema DEBE usarlo
  sin modificar el audio final del video: un MP3 se copia sin recodificar; un WAV se
  codifica a AAC 192 kbps. El guion es opcional en ese caso.
- **FR-012:** El sistema DEBE excluir las etiquetas del guion del texto enviado al TTS
  y al análisis de visemas; del análisis de visemas se excluye además cualquier otra
  marca entre corchetes. Los guiones originales son texto plano, sin corchetes.
- **FR-013:** SI el proveedor TTS elegido falla (sin internet, cuota agotada, webapp
  no disponible), ENTONCES el sistema DEBE detenerse con un mensaje que explique la
  causa y sugiera entregar un audio propio.
- **FR-014:** El sistema DEBE generar en lote los audios de una carpeta de guiones con
  el proveedor TTS elegido, guardando `<id>.mp3` junto a `<id>.txt`, con reintentos
  ante límites de cuota y errores de red, y de forma reanudable (sin regenerar los
  audios ya existentes).
- **FR-015:** El sistema DEBE permitir elegir el género de la voz (hombre o mujer) con una
  sola opción en la configuración (`tts.yaml`) o en la CLI (`--genero`), de modo que cambiar
  de profesor o profesora no exija tocar nada más. El género por defecto es hombre y la voz
  masculina por defecto de Gemini es `es-419-podcaster-3`.

### Lipsync
- **FR-020:** El sistema DEBE obtener una línea de tiempo de visemas (A, B, C, D, E,
  F, G, H, X) a partir del audio, usando el guion como apoyo cuando exista y el
  reconocedor lo admita (se decide tras el spike S1 del plan).
- **FR-021:** El sistema DEBE funcionar con audio en español, en inglés y mezclado: las
  clases A1–A2 (MCER) hablan sobre todo en español con vocabulario en inglés, y las
  B1–B2, al revés, más inglés que español. El reconocedor por defecto de Rhubarb es
  solo para inglés; la elección del reconocedor se decide en el spike S1 (ver
  `research.md`).
- **FR-022:** El sistema DEBE suavizar la línea de tiempo para que ningún visema dure
  menos de 2 frames, salvo los cierres de boca (A) en consonantes M/B/P.

### Render
- **FR-030:** El sistema DEBE componer cada frame con las capas: fondo del escenario
  activo, cuerpo de la pose activa, ojos (abiertos o cerrados) y la boca del visema
  activo, aplicando el plano activo.
- **FR-031:** El sistema DEBE producir un MP4 H.264 (yuv420p) a 25 fps, horizontal
  16:9, con resolución por defecto de 1280×720, configurable a 1920×1080, con el audio
  muxeado.
- **FR-032:** El sistema DEBE escribir los frames en streaming al codificador.
- **FR-033:** El sistema DEBE escribir el MP4 de forma atómica: una interrupción nunca
  deja un archivo con el nombre final.

### Animación secundaria (US3)
- **FR-040:** El sistema DEBE generar parpadeos con intervalos aleatorios de 2 a 6 s
  y una duración de 3 a 5 frames, reproducibles con una semilla. **(v3)** El parpadeo
  intercambia, solo en la zona de los ojos, la imagen de ojos cerrados de la pose
  (`<pose>_parpadeo.png`, imagen completa de la pose con los ojos cerrados); el resto de la
  cabeza se conserva idéntico para que no haya parpadeo de otras partes. Si la pose no tiene
  esa imagen, usa el parche de ojos cerrados de otra pose (`ojos_de`).
  **(v3.1, 2026-10-16)** Se importa como un recorte con borde suave (`parpadeo_cerrado.png` y, en las frontales,
  `parpadeo_medio.png`) por pose: las frontales comparten un solo juego de imágenes (la cabeza casi no cambia);
  cada 3/4 trae el suyo. El recuadro de los ojos se fija por pose en el Editor de poses.
- **FR-041:** El sistema DEBE poder aplicar una "respiración" (escala del cuerpo de ±0.5 %
  con una onda lenta) cuando la pose lo active en su configuración. **Desactivada por
  defecto** (el usuario la descartó el 2026-10-14 por poco natural).
- **FR-042:** MIENTRAS el personaje hable y la pose lo active en su configuración, el
  sistema DEBE aplicar un movimiento leve y suavizado de cabeza o cuerpo, sin saltos entre
  frames consecutivos. **Desactivado por defecto** (descartado por el usuario el 2026-10-14).
- **FR-043 (v3):** El parpadeo DEBE variar para no verse mecánico: con una probabilidad
  configurable (10 % por defecto) el parpadeo es doble, y nunca cae en el mismo frame que un
  cambio de pose.
- **FR-044 (v3):** El sistema DEBE alternar entre las variantes de reposo (p. ej.
  `frontal_neutro_01` a `_04`) cada 6 a 20 s, en una pausa de la voz, con una mezcla de 2
  frames, sin repetir la misma variante dos veces seguidas y de forma reproducible con la
  semilla, para que el personaje no quede inmóvil.
- **FR-045 (v3):** Los gestos de tipo *acento* DEBEN durar entre 3 y 6 s y volver solos a una
  variante de reposo; no puede haber más de un acento cada 20 s (configurable).
- **FR-046 (v3):** Todos los valores de naturalidad (intervalos, probabilidades, duraciones)
  DEBEN poder ajustarse en el archivo de reglas, con valores por defecto, y cada
  comportamiento DEBE poder desactivarse por separado.

### Poses, escenarios y planos (US4)
- **FR-050:** El sistema DEBE mantener una biblioteca de poses por personaje, cada una
  con su cuerpo, su calibración de bocas y, si existe, su imagen de ojos cerrados. **(v3)** Cada
  pose declara su `vista`, su `gesto`, su tipo (estado o acento) y su variante. Una pose puede
  reutilizar las bocas de otra (`bocas_de`) y, por separado, los ojos de otra (`ojos_de`): así
  una pose con gafas y otra sin gafas comparten boca pero tienen ojos cerrados distintos.
- **FR-051 (v3):** CUANDO una pose declare `espejo: true`, el sistema DEBE reflejar
  horizontalmente las formas de boca de esa pose (porque su cabeza mira al lado contrario del de
  las bocas generadas) y sus coordenadas; además, cada forma puede declarar `m: true` para
  invertir su propio reflejo (los dos reflejos se combinan: con ambos activos se anulan). El
  reflejo de la imagen de la pose no se usa si lleva texto (p. ej. el logo de la camisa).
- **FR-052:** El sistema DEBE mantener una biblioteca de escenarios (imagen de fondo
  16:9) y permitir que cada escenario declare opcionalmente los planos y poses que
  admite; por defecto admite todos.
- **FR-053:** El sistema DEBE aplicar el plano como cámara virtual (zoom y recorte
  sobre la composición, con el fondo desenfocado de forma creciente en planos cerrados)
  sin requerir imágenes adicionales por plano, y DEBE avisar cuando la resolución de
  la pose no alcance para un plano pedido.
- **FR-054:** CUANDO el guion contenga una etiqueta de toma, el sistema DEBE cambiar a
  esa toma con un corte directo en la pausa (visema X) más cercana al punto de la
  etiqueta, con una tolerancia de ±2 s; si no hay pausa a ese alcance, DEBE avisar y
  cambiar en el límite de frase más cercano.
- **FR-055:** Las etiquetas DEBEN admitir forma parcial: lo que no se indica se hereda
  de la toma activa (p. ej. cambiar solo el plano).
- **FR-056:** SI una etiqueta referencia una pose, escenario o plano inexistente o no
  admitido, ENTONCES el sistema DEBE detenerse antes de renderizar e informar la línea
  del guion y las opciones válidas.
- **FR-057 (v3):** El escenario PUEDE ser un video MP4 (1080p o más). El sistema DEBE repetirlo
  en bucle durante toda la clase, con un fundido de empalme entre el final y el principio
  (1 s por defecto, configurable) y adaptado a 25 fps, leyéndolo en streaming (un frame cada
  vez, sin acumularlo en memoria).
- **FR-058 (v3):** El plano (cámara virtual) DEBE aplicarse también al fondo en video
  (recorte y escala sobre el video), con el mismo encuadre que sobre la pose.
- **FR-059 (v3):** En un cambio de pose, el sistema DEBE alinear la cabeza de la pose entrante
  con la de una referencia de su vista, por el pelo, desplazando también las bocas, para
  reducir el salto visible en el corte (medido en el prototipo: salto medio de 47 a 26 px). La
  alineación DEBE poder desactivarse. Una cabeza generada con otro giro puede seguir mostrando
  un salto residual.

### Director automático (US9)
- **FR-090:** CUANDO el guion no tenga etiquetas o solo parciales, el sistema DEBE
  elegir las tomas faltantes con reglas: duración mínima de cada toma, sin repetir la
  misma pose de forma consecutiva, cambio de plano de un paso a la vez, y variedad de
  poses y escenarios.
- **FR-091:** Las etiquetas manuales DEBEN tener prioridad sobre el director.
- **FR-092:** El director DEBE respetar las restricciones de planos y poses que declare
  cada escenario (FR-052).
- **FR-093:** Con la misma entrada y la misma semilla, el director DEBE producir las
  mismas tomas.
- **FR-094:** Las reglas del director DEBEN poder ajustarse en un archivo de
  configuración, con valores por defecto.
- **FR-095 (v3):** El director DEBE elegir gestos con un diccionario de palabras clave por
  idioma (español e inglés) configurable: por ejemplo «great» o «genial» disparan un gesto de
  aprobación y «?» una pregunta. Las etiquetas manuales mandan (FR-091), y una clase sin
  coincidencias usa solo variantes de reposo (FR-044).
- **FR-096 (v3):** El director DEBE colocar el gesto en la pausa más cercana a la palabra
  clave (tolerancia ±2 s, como FR-054) y registrar en el log qué gesto eligió y por qué.

### Producción en lote (US10)
- **FR-100:** El sistema DEBE mantener una cola persistente de trabajos; cada trabajo es
  una clase con su audio, guion opcional, personaje, escenarios y semilla.
- **FR-101:** El sistema DEBE crear trabajos desde un manifiesto de lote (una fila por
  clase) con al menos 20 clases, etiquetando el lote.
- **FR-102:** El sistema DEBE procesar varios trabajos en paralelo con un número de
  trabajadores configurable.
- **FR-103:** El fallo de un trabajo NO DEBE detener la cola; el sistema DEBE
  registrarlo con su causa y continuar.
- **FR-104:** Tras una interrupción (cierre, corte de energía), el sistema DEBE
  reanudar sin repetir los trabajos ya terminados.
- **FR-105:** El sistema DEBE mostrar el progreso por trabajo y por lote, con tiempos
  y errores.
- **FR-106:** El sistema DEBE verificar el espacio libre en disco antes de cada trabajo
  y detener la cola con un aviso cuando baje de un umbral configurable.
- **FR-107:** La semilla de cada clase DEBE poder derivarse de forma determinista de
  su identificador, para que repetir un lote reproduzca los mismos videos.
- **FR-066:** El sistema DEBE ofrecer un comando que cree el manifiesto de lote a partir
  de una carpeta de guiones y audios (`clases/<id>.txt` + `<id>.mp3`).

### Assets y calibración (US5)
- **FR-060:** El sistema DEBE incluir un set de bocas placeholder generadas por
  código, para probar el pipeline sin assets definitivos.
- **FR-061:** El sistema DEBE validar, antes de renderizar, que todas las bocas de una
  pose existan, sean PNG con transparencia y tengan el mismo tamaño, y que los nombres
  de archivos respeten la nomenclatura.
- **FR-062 (v3):** El sistema DEBE permitir fijar, para cada pose, la posición, el tamaño, el
  giro y el reflejo de **cada forma de boca por separado** (cambiar una no altera las demás),
  con una herramienta visual (arrastrar sobre la imagen, vista ampliada, forma «fantasma» de
  comparación, animar la secuencia) y guardarlos en la configuración de la pose. La herramienta
  DEBE poder traer los valores de otra pose desplazados según la posición de la cabeza, y
  exportar e importar la calibración de todas las poses en un solo archivo.
- **FR-063:** El sistema DEBE generar una previsualización de 5 segundos.
- **FR-064:** El sistema DEBE permitir, desde la interfaz web local, agregar poses,
  bocas y escenarios arrastrando archivos o eligiéndolos con un selector, y guardarlos
  en la carpeta correcta con los nombres correctos, validándolos (FR-061) al subirlos.
  También DEBE poder hacerse copiando los archivos a mano. Los archivos viven en
  carpetas del proyecto.
- **FR-065:** El sistema DEBE incluir un README de assets que recuerde la forma de cada
  boca (visemas A–H y X), la calidad y resolución de imagen recomendadas, el formato,
  la nomenclatura, el catálogo de planos, una guía de continuidad para cambios de toma
  naturales y un prompt plantilla para pedir a una IA externa que etiquete un guion.
  DEBE informar al usuario dónde queda la carpeta de assets.
- **FR-067 (v3):** Cada vista (frontal, tres cuartos) DEBE tener su propio juego de bocas; las
  poses de una vista usan el de esa vista. Las bocas 3/4 se generan para cabezas que miran a la
  derecha y se reflejan para las que miran a la izquierda (FR-051).

### Interfaces (US6)
- **FR-070:** El sistema DEBE ofrecer una CLI:
  `python -m src.render --guion <txt> --personaje <nombre> [--audio <archivo>] [--tts gemini-studio|edge] [--genero hombre|mujer] [--resolucion 1280x720|1920x1080] [--seed N]`
  y comandos equivalentes para la cola y los lotes.
- **FR-071:** El sistema DEBE ofrecer una interfaz web local con: guion, voz o audio,
  personaje, escenario, resolución, botón de render, reproductor y descarga.
- **FR-072:** *Retirado de la Fase 1* (ver sección 10).

### Preparación de assets desde una imagen única (US8)
- **FR-080:** El sistema DEBE separar al personaje del fondo a partir de una imagen
  única, generando `cuerpo.png` con transparencia, usando una herramienta local y
  gratuita de segmentación (la elección se justifica en `research.md`).
- **FR-081:** El sistema DEBE poder reconstruir el fondo en la zona donde estaba el
  personaje (inpainting local y gratuito) para generar un escenario limpio a partir de
  la imagen original.
- **FR-082:** El sistema DEBE permitir revisar y corregir manualmente la máscara del
  personaje (exportar la máscara como PNG editable y volver a importarla), porque la
  segmentación automática puede fallar en bordes como el pelo, los lentes o el libro.
- **FR-083:** El sistema DEBE ofrecer un modo de respaldo sin separación: usar la
  imagen completa como capa base de una toma fija y animar solo boca y ojos (parpadeo
  sí; sin respiración ni movimiento leve).
- **FR-084:** La preparación de assets DEBE ejecutarse una sola vez por pose y guardar
  los resultados en la carpeta de la pose; los renders posteriores no deben repetirla.
- **FR-085:** CUANDO la imagen original no sea 16:9, el sistema DEBE informarlo y
  ofrecer recortar o rellenar el fondo, sin deformar al personaje; y DEBE avisar, sin
  bloquear, si es menor que la resolución de salida pedida.

## 6. Requisitos no funcionales

- **NFR-001 (Memoria):** el pico de RAM de un trabajo se mantiene por debajo de 2 GB y
  no crece con la duración del audio (verificado con audios de 1 y 10 minutos).
- **NFR-002 (Rendimiento individual):** un audio de 5 minutos se renderiza a 1280×720
  en un solo trabajo, en CPU, en ≤ 10 minutos (la preparación de assets no cuenta).
- **NFR-003 (Sincronía):** el desfase entre audio y visemas es ≤ 1 frame (40 ms).
- **NFR-004 (Reproducibilidad):** misma entrada y misma semilla producen frames
  idénticos.
- **NFR-005 (Portabilidad):** funciona en rutas con espacios y acentos en Windows
  (caso real: `C:\Users\Juan 02\...`).
- **NFR-006 (Errores):** todo error visible al usuario está en español e indica qué
  hacer para corregirlo.
- **NFR-007 (Rendimiento en lote):** en el equipo de referencia, el tiempo efectivo
  medio es ≤ 2 minutos por clase de 5 minutos a 1280×720 con los trabajadores en
  paralelo (equivale a ≈ 16 horas continuas para 480 clases). Es una meta; se valida
  con mediciones en la Fase 3.
- **NFR-008 (Espacio):** el MP4 de una clase de 5 minutos a 1280×720 pesa en promedio
  ≤ 60 MB, de modo que 480 clases caben en ≤ 30 GB, muy por debajo de los 700 GB libres.
- **NFR-009 (Robustez de lote):** la memoria total con N trabajadores es N × el límite
  de NFR-001 y no crece durante el lote.

## 7. Criterios de aceptación por requisito

Cada requisito se verifica con al menos un test automatizado (P6).

| Requisito | Criterio de aceptación | Tipo |
|---|---|---|
| FR-001 | En una carpeta limpia, el instalador deja ffmpeg, Rhubarb y los modelos dentro del proyecto, con checksums verificados. | Auto + manual |
| FR-002 | Con todo instalado, la verificación reporta "OK" por dependencia; al quitar una, reporta cuál falta y qué hacer. | Auto |
| FR-010 | Sin `--audio`, se produce un audio con cada uno de los 3 proveedores; sin `--tts`, se usa `gemini-studio`. | Auto (Gemini con doble de prueba; real manual) |
| FR-011 | Con MP3, el flujo de audio del MP4 es idéntico al entregado (sin recodificar); con WAV se obtiene AAC 192 kbps; en ambos casos la duración coincide y el render funciona sin guion. | Auto |
| FR-012 | Un guion con etiquetas entrega al TTS y al análisis un texto sin etiquetas. | Auto |
| FR-013 | Con el proveedor forzado a fallar, el sistema sale con error y un mensaje en español con la causa y la alternativa de entregar un audio propio. | Auto |
| FR-014 | Con 3 guiones y un doble de prueba que falla en la 2.ª petición, se generan los 3 audios tras el reintento; relanzar el comando no regenera los existentes. | Auto |
| FR-015 | Con `genero: hombre` cada proveedor usa su voz masculina y con `mujer` la femenina; `--genero` manda sobre el archivo; una `voz` explícita manda sobre el género; un valor inválido se rechaza con mensaje en español. | Auto |
| FR-020 | Para un audio de prueba, la línea de tiempo cubre toda la duración y solo usa visemas A–H, X. | Auto |
| FR-021 | Con un audio de prueba en español, la línea de tiempo no es degenerada (hay variedad de visemas). | Auto + manual |
| FR-022 | Ningún visema dura < 2 frames, salvo A en M/B/P. | Auto |
| FR-030 | Un frame de prueba coincide con la composición esperada (fondo, cuerpo, ojos, boca, plano) en assets sintéticos. | Auto |
| FR-031 | `ffprobe` del MP4 reporta H.264, yuv420p, 25 fps, 16:9 horizontal, la resolución pedida y una pista de audio. | Auto |
| FR-032 | El render no acumula frames en memoria (ver NFR-001). | Auto |
| FR-033 | Interrumpir un render no deja un MP4 con el nombre final; al terminar bien, el archivo final existe y es reproducible. | Auto |
| FR-040 | Intervalos entre parpadeos en [2, 6] s y duraciones en [3, 5] frames; misma semilla, mismos parpadeos; con imagen de ojos cerrados solo cambian los píxeles de la zona de los ojos. | Auto |
| FR-041 | Con la respiración activada, la escala oscila dentro de ±0.5 % y es continua; por defecto la escala es siempre 1. | Auto |
| FR-042 | Con el movimiento activado hay desplazamiento solo mientras hay habla y la diferencia entre frames consecutivos no supera un umbral de suavidad (35 % de la amplitud); por defecto no hay desplazamiento. | Auto |
| FR-043 | En 1.000 parpadeos simulados, la fracción de dobles está dentro de ±3 puntos de la probabilidad configurada y ninguno coincide con un cambio de pose. | Auto |
| FR-044 | En una clase de 5 min con 4 variantes, ningún par consecutivo repite variante, los cambios caen en pausas con mezcla de 2 frames y la misma semilla da la misma secuencia. | Auto |
| FR-045 | Un acento nunca dura menos de 3 s ni más de 6 s, vuelve a una variante de reposo y no hay más de uno cada 20 s. | Auto |
| FR-046 | Cambiar un valor de naturalidad en el archivo de reglas cambia el comportamiento sin tocar el código; cada comportamiento se puede apagar. | Auto |
| FR-050 | Una biblioteca con 2+ poses renderiza usando las capas, bocas y anclas propias de cada una; cada pose expone vista, gesto, tipo y variante. | Auto |
| FR-051 | Con `espejo: true` las bocas y sus coordenadas son el reflejo horizontal exacto; con `m: true` en una forma solo esa forma invierte; con ambos activos vuelve a su orientación original. | Auto |
| FR-052 | Un escenario con restricciones solo admite los planos y poses declarados; sin restricciones admite todos. | Auto |
| FR-053 | Cada plano PL1–PL6 produce el encuadre esperado sobre la misma pose; con resolución insuficiente se emite el aviso. | Auto |
| FR-054 | El cambio de toma ocurre en el visema X más cercano, dentro de ±2 s; sin pausa a ese alcance se avisa y se usa el límite de frase. | Auto |
| FR-055 | Una etiqueta parcial cambia solo lo indicado y conserva lo demás. | Auto |
| FR-056 | Una etiqueta inválida detiene el proceso antes del primer frame, indicando línea y opciones válidas. | Auto |
| FR-057 | Con un video de 15 s y una clase de 280 s, el fondo se repite sin que la diferencia entre frames consecutivos en la unión supere la de una zona normal; se lee un frame cada vez (RAM constante). | Auto |
| FR-058 | Con el plano busto, el fondo en video y la pose comparten el mismo recorte y escala. | Auto |
| FR-059 | En una serie de cortes de prueba, el salto medio de la cara con la alineación es menor que sin ella y la alineación se puede desactivar. | Auto |
| FR-060 | Existe un set completo de bocas placeholder (A–H, X) que pasa FR-061 sin assets del usuario. | Auto |
| FR-061 | Bocas faltantes, sin canal alfa, de distinto tamaño o con nombre inválido producen un error que nombra el archivo y el problema. | Auto |
| FR-062 | Tras calibrar una forma en una pose, las otras ocho formas conservan sus valores; la configuración de la pose guarda posición, tamaño, giro y reflejo de las nueve; «traer valores» desplaza según la cabeza; exportar e importar todas las poses reproduce exactamente la calibración. | Auto (lógica) + manual (herramienta) |
| FR-063 | La previsualización dura 5 s (±1 frame) y se genera mucho más rápido que un render completo. | Auto |
| FR-064 | Al soltar un PNG válido en la UI aparece en la carpeta correcta con el nombre correcto; uno inválido se rechaza con mensaje en español; copiar a mano da el mismo resultado. | Auto (lógica) + manual (UI) |
| FR-065 | El README existe y cubre: formas de visemas, resolución, formato, nomenclatura, planos, guía de continuidad y prompt plantilla; la ruta de la carpeta se muestra. | Revisión manual |
| FR-067 | Una pose frontal usa el juego frontal y una 3/4 el 3/4; una cabeza que mira a la izquierda usa el juego 3/4 reflejado. | Auto |
| FR-070 | La CLI acepta todos los argumentos indicados y rechaza valores inválidos con mensaje en español. | Auto |
| FR-071 | Desde la web local se completa un render de principio a fin y se descarga el MP4. | Manual + Auto (lógica) |
| FR-080 | `cuerpo.png` tiene transparencia y excluye el fondo en una imagen de prueba con máscara conocida (IoU mínimo definido en el plan). | Auto + manual |
| FR-081 | El escenario generado no tiene huecos (sin píxeles transparentes) donde estaba el personaje. | Auto + manual |
| FR-082 | Exportar la máscara, editarla y reimportarla produce un `cuerpo.png` coherente con la máscara editada. | Auto |
| FR-083 | En modo de respaldo se renderiza una toma fija con boca y ojos animados, con parpadeo y sin respiración ni movimiento leve. | Auto |
| FR-084 | Un segundo render con la pose ya preparada no ejecuta segmentación ni inpainting. | Auto |
| FR-085 | Una imagen 4:3 genera el aviso y las opciones recortar/rellenar sin deformar al personaje; una imagen menor que la salida genera un aviso que no bloquea. | Auto |
| FR-090 | Sin etiquetas, la secuencia de tomas respeta duración mínima, no repite pose consecutiva, cambia el plano de a un paso y varía poses y escenarios. | Auto |
| FR-091 | Una etiqueta manual se respeta y el director decide solo el resto. | Auto |
| FR-092 | El director nunca elige una combinación que el escenario no admita. | Auto |
| FR-093 | Misma entrada y misma semilla producen la misma secuencia de tomas. | Auto |
| FR-094 | Cambiar un valor en el archivo de reglas cambia el comportamiento sin tocar el código. | Auto |
| FR-095 | Con el diccionario «great/genial → aprobación», un guion que contiene esas palabras produce un acento de aprobación en la pausa más cercana; sin coincidencias solo hay variantes de reposo; una etiqueta manual manda. | Auto |
| FR-096 | El gesto se coloca dentro de ±2 s de la palabra clave y el log indica gesto, palabra y pausa elegida. | Auto |
| FR-100 | Los trabajos encolados persisten tras cerrar y reabrir el sistema. | Auto |
| FR-101 | Un manifiesto de 20 clases crea 20 trabajos con la etiqueta del lote; un manifiesto con errores indica fila y problema. | Auto |
| FR-102 | Con N trabajadores se procesan N trabajos a la vez, sin pisarse archivos. | Auto |
| FR-103 | Con un trabajo defectuoso en un lote de 20, se terminan 19 y el fallo se reporta con su causa. | Auto |
| FR-104 | Tras matar el proceso a mitad de un lote, la reanudación no repite trabajos terminados y rehace los interrumpidos. | Auto |
| FR-105 | El estado muestra progreso, tiempos y errores por trabajo y por lote. | Auto + manual |
| FR-106 | Con el espacio libre bajo el umbral, la cola se detiene con un aviso en español y retoma al liberar espacio. | Auto |
| FR-107 | Dos ejecuciones del mismo lote producen los mismos videos (hash de frames). | Auto |
| FR-066 | Con `clases/` de 20 guiones y audios, el comando genera un manifiesto de 20 filas; los guiones sin audio o los audios sin guion se reportan. | Auto |
| NFR-001 | Pico de RAM < 2 GB por trabajo con audios de 1 y 10 minutos, sin diferencia significativa. | Auto (medición) |
| NFR-002 | Audio de 5 min a 1280×720 en CPU, un trabajo, en ≤ 10 min. | Auto (medición) |
| NFR-003 | Desfase medido entre el visema esperado y el mostrado ≤ 40 ms. | Auto |
| NFR-004 | Dos renders con misma entrada y semilla producen frames idénticos (hash). | Auto |
| NFR-005 | La suite de integración pasa en una ruta con espacios y acentos. | Auto |
| NFR-006 | Cada caso borde de la sección 9 produce un mensaje en español con una acción correctiva. | Auto |
| NFR-007 | Un lote de 20 clases de 5 min en el equipo de referencia promedia ≤ 2 min efectivos por clase. | Auto (medición) |
| NFR-008 | El tamaño medio del MP4 de 5 min a 1280×720 es ≤ 60 MB. | Auto (medición) |
| NFR-009 | La RAM total de un lote con N trabajadores no supera N × 2 GB ni crece durante el lote. | Auto (medición) |

## 8. Entidades clave (sin detalle de implementación)

- **Personaje:** conjunto nombrado de poses.
- **Pose, Escenario, Plano, Toma:** ver sección 4.
- **Guion:** texto de la clase, con etiquetas opcionales de toma.
- **Línea de tiempo:** secuencia de visemas, tomas y parpadeos sobre el eje de tiempo
  del audio.
- **Trabajo:** una clase por renderizar (audio, guion opcional, personaje, escenarios,
  semilla, estado).
- **Lote:** conjunto etiquetado de trabajos creado desde un manifiesto.
- **Video final:** MP4 H.264 con audio, en `salidas/` con nombre derivado del guion o
  del identificador de la clase y la fecha.

## 9. Casos borde a cubrir

- Silencio largo al inicio o final del audio.
- Audio de más de 10 minutos.
- MP3 con frecuencia de muestreo distinta.
- Guion con números, siglas y abreviaturas (afecta al TTS).
- Guion vacío, solo con etiquetas, o ausente con audio propio.
- Etiqueta de toma mal escrita o no admitida por el escenario.
- Bocas con tamaños distintos, sin canal alfa o con nombre inválido.
- Fallo o ausencia del binario de Rhubarb.
- TTS no disponible (sin internet, cuota de Gemini agotada, webapp apagada).
- Imagen original que no es 16:9 o de baja resolución; pose sin resolución suficiente
  para un plano cerrado.
- Segmentación que corta parte del personaje (lentes, libro, mano).
- Interrupción del render a mitad: no debe dejar un MP4 corrupto con el nombre final.
- Escenario que no admite ninguna pose o plano disponible.
- Disco lleno o con poco espacio durante un lote.
- Apagado de la PC en medio de un lote.
- Trabajos duplicados en la cola o manifiesto con filas inválidas.
- **(v3)** Video de fondo más corto que el fundido de empalme, sin audio o con otra resolución o
  velocidad de fotogramas.
- **(v3)** Pose cuya cabeza difiere mucho de la de referencia (giro distinto): salto residual en
  el corte aunque se alinee.
- **(v3)** Imagen de ojos cerrados que cambia algo más que los ojos: solo se aplica la zona de
  los ojos.
- **(v3)** Pose sin imagen de ojos cerrados ni `ojos_de`: no parpadea y se avisa.
- **(v3)** Una forma de boca regenerada con otro tamaño: se conserva su calibración por forma y
  se avisa de que hay que revisarla.
- **(v3)** Logo o texto en la camisa y reflejo de la imagen de la pose.

## 10. Fuera de alcance (Fase 1)

Video del personaje en loop (el fondo en video sí entra en la Fase 1), tracking de cara, máscaras sobre video, MuseTalk o cualquier
lipsync neuronal, generación de bocas, poses o escenarios con IA.

La segmentación y el inpainting de FR-080/FR-081 son procesamiento de imagen local
para preparar assets, NO generación con IA; por eso sí entran en la Fase 1. Pueden
usar la GPU si está disponible, pero deben funcionar también en CPU.

También quedan fuera de la Fase 1:
- Subtítulos .srt (antes US7/FR-072). El usuario ya tiene otra webapp local que corta
  silencios y pone subtítulos animados; los silencios se cortan después del render, en
  esa herramienta.
- APIs entre webapps locales. Hoy no existen; construirlas es un trabajo aparte, en
  otra conversación.
- Etiquetado automático del guion mediante llamada a la API de Gemini (requeriría
  enmendar la constitución P2). En la Fase 1 se ofrece un prompt plantilla para
  hacerlo manualmente con cualquier IA (FR-065).
- Ángulos de cámara distintos del normal como cámara virtual (se resuelven como poses
  distintas; las vistas 3/4 entran como poses con su propio juego de bocas, FR-067), plano
  detalle y transiciones con fundido (solo corte directo, salvo la mezcla de 2 frames entre
  variantes de reposo, FR-044).
- Dirección sensible al significado completo del texto (cerrar el plano en una frase importante); la elección de gestos por palabras clave sí entra (FR-095).

## 11. Criterios de éxito medibles

- **SC-001 (Hito 1):** a partir de la imagen única del personaje, un video de 10
  segundos a 1280×720 con bocas placeholder, sincronizado y reproducible en VLC y en
  el navegador (vale con el modo de respaldo de FR-083 si la separación aún no está
  lista).
- **SC-002:** una clase de 5 minutos con assets reales, sin intervención manual
  después de pulsar "Render".
- **SC-003:** un usuario nuevo deja el entorno funcionando solo con el instalador y
  `quickstart.md`.
- **SC-004:** un lote de 20 clases de 5 minutos se completa sin intervención, con
  fallos aislados reportados.
- **SC-005:** un lote de 500 clases se completa en ≤ 20 horas continuas en el equipo
  de referencia.
- **SC-006 (plazo):** las 480 clases de 5 minutos están renderizadas y entregadas a
  más tardar el 20 de diciembre de 2026.
- **SC-007 (v3):** una clase de 5 minutos con fondo en video, cambios de pose, parpadeo y
  variantes de reposo se completa en ≤ 2 minutos efectivos por clase (el prototipo sin
  parpadeo midió ≈ 60 s con un trabajador, 13–21 MB por MP4).

## 12. Clarificaciones

Sin marcadores `[NEEDS CLARIFICATION]` pendientes.

### Resueltas
- **Resolución:** 16:9 horizontal, 1280×720 por defecto y para la producción masiva
  (configurable a 1920×1080).
- **Capas e imagen única:** el usuario entrega una imagen con personaje y fondo
  unidos; el sistema extrae la pose y, opcionalmente, el escenario (US8).
- **Voz:** webapp local `gemini-tts-studio` (`http://127.0.0.1:5055/`, carpeta
  `C:\Users\Juan 02\Desktop\gemini-tts-studio`), proveedor por defecto; se analiza en
  la Fase 3. La variante de español la define esa webapp; para `edge` se
  elegirá la voz más cercana en `research.md`.
- **API key (constitución v1.1, P2):** herramienta estrictamente local; sin
  restricciones especiales sobre su manejo.
- **Guion con audio propio:** opcional; se recomienda entregar audio y texto juntos.
- **Subtítulos y APIs entre webapps:** fuera de la Fase 1.
- **Modo de respaldo:** parpadeo sí; respiración y movimiento leve no.
- **Baja resolución:** se avisa, sin bloquear.
- **Salidas:** carpeta `salidas/` del proyecto.
- **Assets definitivos:** los aporta el usuario, trabajados con una IA externa, con
  ayuda del README de assets (FR-065) y de la subida por UI (FR-064).
- **Modelo estudio:** biblioteca de poses + biblioteca de escenarios + plano como
  cámara virtual; ángulo solo normal en la Fase 1.
- **Dirección de tomas:** director automático por reglas como camino por defecto, con
  etiquetas opcionales que tienen prioridad.
- **Lotes:** cola persistente con trabajadores en paralelo; un lote de 20 y una cola de
  lotes son lo mismo (trabajos agrupados).
- **Espacio:** 700 GB libres para salidas.
- **(v3) Bocas elegidas:** hoja de dibujo animado frontal y su versión 3/4 (ambas generadas con
  IA, sin licencia que reclamar); calibración por pose y por forma, cerrada por el usuario el
  2026-10-15.
- **(v3) Fondo en video:** probado con un clip de 15 s en bucle con fundido de 1 s; render de
  una clase de 4:40 en ≈ 60 s con un trabajador.
- **(v3) Naturalidad:** la respiración y el movimiento de cabeza siguen descartados
  (FR-041/042); la sensación de vida se logra con variantes de reposo, parpadeo variado y
  acentos. El parpadeo usa una imagen de ojos cerrados por pose, que aporta el usuario.

### Supuestos a confirmar al aprobar
- **(v3)** Alineación de cabezas por el pelo y mezcla de 2 frames entre variantes de reposo
  (FR-059, FR-044): valores iniciales a validar con el usuario.
- **(v3)** Intervalos de naturalidad por defecto (variantes cada 6–20 s, un acento cada 20 s
  como máximo, 10 % de parpadeos dobles): propuestos, ajustables en el archivo de reglas.
- **(v3)** Solo hay una variante de reposo 3/4 (`tres_cuartos_der_neutro_01`) frente a cuatro
  frontales: para alternar variantes en 3/4 el usuario debe generar más.
- Corte directo con tolerancia de ±2 s para los cambios de toma (FR-054), propuesto y
  no objetado.
- Meta de ≤ 2 min efectivos por clase (NFR-007). El plazo (20 de diciembre de 2026,
  68 días desde el 13 de octubre) exige como mínimo ≈ 8 min efectivos por clase si
  se reservan ≈ 45 días de render continuo; la meta de 2 min deja un margen de 4×
  para desarrollo, preparación de assets y generación de audio.
- Tamaño medio ≤ 60 MB por MP4 (NFR-008), derivado de los 700 GB disponibles.

## 13. Changelog

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-13 | Versión inicial del borrador. | Fase 1 de SDD. |
| 2026-10-13 | Resueltas CL-01 a CL-07; añadidos FR-064 y FR-065; retirados US7 y FR-072; APIs entre webapps fuera de alcance. | Respuestas del usuario. |
| 2026-10-14 | FR-041 y FR-042 (respiración y movimiento leve) pasan a opcionales y desactivados por defecto; FR-050 añade `ojos_de` independiente de `bocas_de` (poses con y sin gafas). | Decisión del usuario tras ver el video con animación. |
| 2026-10-14 | Piper retirado por calidad (constitución v1.2: P1 admite Gemini de pago, P2 sin voz offline obligatoria); FR-010, FR-013 y FR-001 sin Piper; añadido FR-015 (género de la voz, defecto hombre, voz `es-419-podcaster-3`). | Decisión del usuario tras escuchar las muestras. |
| 2026-10-14 | Aprobado `tasks.md`. FR-021 amplía el idioma a español, inglés y mezclado (A1–A2 sobre todo español; B1–B2 sobre todo inglés); FR-012 aclara que los guiones originales no llevan corchetes y que el análisis de visemas descarta cualquier marca entre corchetes; el problema (sección 1) menciona los tres casos. | Aclaración del usuario tras revisar `Temp Real Assest Testing`. |
| 2026-10-14 | Aprobados CP-1 a CP-4 del plan: añadidos FR-014 y FR-066; precisados FR-011 y FR-020. | Aprobación del usuario del plan y sus cambios. |
| 2026-10-13 | Spec v2 aprobada por el usuario con los tres supuestos de la sección 12 (plazo 2026-12-20). Los guiones de las clases existen sin organizar; el manifiesto de lote se derivará de una carpeta de guiones y audios. | Aprobación del usuario. |
| 2026-10-13 | Añadido SC-006 (plazo 2026-12-20) y justificación del plazo en NFR-007. | El usuario indicó el plazo límite. |
| 2026-10-13 | v2: modelo estudio (poses, escenarios, plano como cámara virtual), director automático (US9, FR-090 a FR-094), producción en lote (US10, FR-100 a FR-107), FR-033, NFR-007 a NFR-009, SC-004 y SC-005, equipo de referencia. Se eliminan el eje ángulo y la nomenclatura E·P·A·PL. | Decisiones del usuario sobre el flujo de producción masiva. |
| 2026-10-15 | v3 (borrador): añadidos US11 a US13, FR-043 a FR-046, FR-057 a FR-059, FR-067, FR-095 y FR-096, SC-007; modificados FR-040, FR-050, FR-051, FR-062 y la nomenclatura de pose (sección 4); casos borde, fuera de alcance, clarificaciones y supuestos actualizados. | Pruebas reales con el usuario: fondo en video, vistas 3/4 con reflejo, gestos, calibración por forma y naturalidad. |
| 2026-10-15 | Spec v3 aprobada por el usuario con sus supuestos (alineación de cabezas por el pelo, mezcla de 2 frames entre variantes de reposo, intervalos de naturalidad por defecto, una sola variante de reposo 3/4 por ahora). Siguiente paso: añadir las tareas de la v3 a `tasks.md`. | Aprobación del usuario. |
| 2026-10-16 | v3.1: el parpadeo por imagen pasa a ser un recorte con borde suave por pose (frontales comparten un juego de cerrado y medio; cada 3/4 trae el suyo); parpadeo doble con probabilidad configurable (10 %) y nunca en un cambio de pose (FR-043); calibración de bocas y recuadros de ojos en el Editor de poses. | Aprobado por el usuario en el chat (puntos 1–3 de la propuesta de organización de bocas y parpadeos). |
| 2026-10-16 | PROPUESTO (pendiente de aprobación): FR-061 se relaja para las poses con calibración por forma; sus bocas pueden medir distinto porque cada forma lleva su propia escala. | Implementado en T093–T096; falta tu OK. |
| 2026-10-16 | v3.2: el director (FR-090 a FR-094, FR-044 a FR-046) ya existe: cambia el plano de la cámara virtual en cada corte (un paso, sin vaivenes), alterna variantes de reposo, mete acentos de 3 a 6 s y mezcla 2 frames al cambiar de pose; reglas en `reglas_director.yaml`. Sin etiquetas manuales ni gestos por palabras clave todavía. | Petición del usuario: usar la cámara virtual para variar los planos. |
| 2026-10-19 | v3.3: el lote usa el pipeline nuevo (poses por vista con director, escenario repartido por clase) y el idioma de cada clase decide voz y reconocedor (FR-021); interfaz web local (`python -m src.ui`, puerto 8780) con guiones, voces, render y lote, hecha con la biblioteca estándar de Python en lugar de Gradio para no añadir dependencias pesadas. | Petición del usuario: cerrar el bloqueante del lote y poder interactuar sin comandos. |
| 2026-10-19 | v3.4: casting de voz cerrado por el usuario: una sola voz masculina (`es-419-podcaster-3`) con perfil «colombiano» (instrucción de acento, por defecto) o «neutro», para español, inglés o mezclado; la interfaz ya no permite cambiar de voz. El catálogo de Gemini no tiene voces colombianas propias (solo argentinas y mexicanas en es-419). | Decisión del usuario tras escuchar las pruebas. |
