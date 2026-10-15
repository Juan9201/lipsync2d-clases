# Constitución del proyecto: Lipsync 2D para clases educativas

**Versión:** 1.2
**Metodología:** Spec-Driven Development (SDD)
**Alcance:** rige toda la Fase 1 y sirve de base para la Fase 2.

Esta constitución contiene los principios no negociables del proyecto. Toda
especificación, plan, tarea y línea de código debe cumplirlos. Si un requisito o una
decisión técnica los contradice, se detiene el trabajo y se pide una enmienda explícita
(ver "Gobernanza").

---

## P1. Costo cero

- **Principio:** solo se usan herramientas gratuitas y de código abierto. Ninguna API
  ni servicio de pago, ni siquiera como opción, **con una única excepción (v1.2):** la
  voz con Gemini TTS a través de la webapp `gemini-tts-studio` puede usar la cuenta de
  pago del usuario, por decisión suya y bajo su propia cuenta.
- **Por qué:** las alternativas probadas (ComfyUI + Wan 2.1 + LatentSync en POD,
  servicios comerciales) son caras; el objetivo del proyecto es evitar ese costo.
- **Cómo se verifica:** cada dependencia, binario y modelo declara su licencia en
  `research.md`. El gasto de Gemini TTS lo asume y controla el usuario; el sistema no
  contrata ni usa ningún otro servicio de pago.

## P2. Local-first

- **Principio:** todo el procesamiento (segmentación, inpainting, lipsync, render,
  encode) corre en la PC del usuario. Solo se permiten proveedores de TTS que usan
  internet: la webapp `gemini-tts-studio` del usuario (cuenta propia, gratuita o de
  pago) y, de forma opcional, `edge-tts` (gratuito).
- **Garantías obligatorias:**
  - (v1.2) Ya no se exige una alternativa de voz 100 % offline: el usuario retiró Piper
    por su calidad. La garantía siguiente asegura que el render nunca queda bloqueado.
  - El pipeline nunca depende de que el TTS esté disponible: también acepta un audio
    ya generado.
  - El proyecto es una herramienta de uso estrictamente local, sin equipo de trabajo
    ni publicación en internet. Por eso no se imponen restricciones especiales al
    manejo de la API key de Gemini del usuario: puede leerse de la configuración de
    su webapp o de un archivo local y reutilizarse dentro del proyecto.
- **Cómo se verifica:** test de render completo sin red con audio propio.

## P3. Memoria acotada

- **Principio:** el consumo de RAM no depende de la duración del video. Los frames se
  escriben en streaming hacia ffmpeg y nunca se acumulan en memoria.
- **Cómo se verifica:** medición de pico de RAM con audios de 1 y 10 minutos (NFR-001).

## P4. Reproducibilidad

- **Principio:** versiones fijadas de dependencias, binarios y modelos, con
  verificación de checksums. Un script deja el entorno listo desde cero. Mismas
  entradas y misma semilla producen la misma salida.
- **Cómo se verifica:** archivo de dependencias con versiones exactas; checksums en el
  instalador; test de determinismo de frames (NFR-004).

## P5. Windows-first

- **Principio:** todo funciona en Windows 10/11, con PowerShell, rutas con espacios y
  acentos (caso real: `C:\Users\Juan 02\...`) y sin requerir permisos de
  administrador. Las rutas se manejan con `pathlib`; nunca se construyen
  concatenando cadenas ni se pasan por un shell sin escapar.
- **Cómo se verifica:** los tests de integración corren en una ruta con espacios y
  acentos (NFR-005).

## P6. Test-first

- **Principio:** cada requisito se verifica con tests automatizados, escritos antes
  del código de producción. Una tarea no está terminada con tests en rojo.
- **Reglas asociadas:**
  - Todo requisito (FR/NFR) tiene al menos un criterio de aceptación y un test.
  - Toda tarea referencia al menos un requisito.
- **Cómo se verifica:** matriz de trazabilidad en `validation.md`.

## P7. Modularidad orientada a la Fase 2

- **Principio:** la capa base del render es intercambiable (imagen estática hoy, video
  en loop mañana) sin reescribir el compositor. Las capas implementan una interfaz
  común (`BaseLayer`) y las anclas de boca y ojos se obtienen a través de un
  proveedor, de modo que puedan ser fijas hoy y por frame mañana.
- **Cómo se verifica:** el plan describe cómo se añadiría una `VideoLoopLayer` sin
  modificar el compositor; un test usa una capa falsa para comprobar que el
  compositor no depende de implementaciones concretas.

## P8. Simplicidad

- **Principio:** ninguna abstracción, opción de configuración o dependencia que no
  exija un requisito actual o la Fase 2. Ante dos soluciones válidas, se elige la más
  simple. No se implementa lo que está fuera de alcance.
- **Cómo se verifica:** en la revisión del plan, cada abstracción justifica el
  requisito que la exige.

## P9. Observabilidad

- **Principio:** logs claros por etapa (preparación de assets, TTS, Rhubarb, render,
  encode), con tiempos por etapa. Todo error visible al usuario está en español e
  indica qué hacer para corregirlo.
- **Cómo se verifica:** tests de los mensajes de error de los casos borde (NFR-006);
  el render imprime un resumen de tiempos por etapa.

---

## Reglas transversales

1. **Idioma:** artefactos, comentarios de código y mensajes al usuario en español.
2. **Salidas atómicas:** un render interrumpido nunca deja un archivo con el nombre
   final; se escribe a un temporal y se renombra al terminar con éxito.
3. **Qué vs. cómo:** la spec describe QUÉ y POR QUÉ; el CÓMO vive en `plan.md`.
4. **Ambigüedad:** lo ambiguo se marca como `[NEEDS CLARIFICATION: pregunta]` y se
   consulta al usuario; no se inventa.
5. **GPU opcional:** la GPU (RTX 3050) puede acelerar la preparación de assets, pero
   ninguna funcionalidad depende de ella.
6. **Sin código antes de tiempo:** no se escribe código de producción hasta que el
   usuario apruebe `spec.md`, `plan.md` y `tasks.md`.

## Gobernanza

- Esta constitución solo se modifica con aprobación explícita del usuario, y cada
  cambio se registra en el historial siguiente.
- Si un plan o una tarea necesita violar un principio, se documenta la violación, su
  justificación y la alternativa más simple descartada, y se espera aprobación. Sin
  aprobación, no se avanza.
- Toda fase (`plan.md` en particular) incluye un chequeo de cumplimiento contra P1–P9.

## Historial de cambios

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 2026-10-13 | Redacción inicial a partir de los insumos del usuario. |
| 1.1 | 2026-10-13 | P2: se elimina la restricción sobre el manejo de la API key (entorno local, sin publicación ni equipo). Sustituye la instrucción "nunca copies ni registres mi API key" del insumo 2.9. |
| 1.2 | 2026-10-14 | P1: excepción para Gemini TTS con la cuenta de pago del usuario. P2: se retira la exigencia de una alternativa de voz offline (Piper descartado por calidad); el render sigue sin depender del TTS. |
