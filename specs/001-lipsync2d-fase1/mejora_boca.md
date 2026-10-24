# Mejora de la animación de la boca — investigación y plan (2026-10-24)

## 1. Cómo lo hacen los estudios y las herramientas profesionales

Fuentes: blogs y notas de curso de animación, documentación de Toon Boom, Adobe y Rhubarb (ver enlaces al final). No hay una norma
publicada única; lo que sigue es lo que coincide entre fuentes.

1. **No se marca cada fonema.** Se eligen las vocales y las consonantes fuertes que la boca tiene que «tocar», y se deja que lo demás
   se resuelva con intermedios. Marcar todo da una boca «aleteando».
2. **Pocas formas.** La carta clásica (Preston Blair) tiene 8–12 formas. Toon Boom usa A–G + X; Rhubarb usa A–H + X (la misma familia);
   Adobe Character Animator, 11 visemas más 3 de reposo/expresión. **Nuestras 9 formas están en el estándar.** Más dibujos no es la palanca.
3. **Tiempo.** Las formas se colocan **1–2 cuadros antes** del sonido (si se ponen justo en el pico del audio, se lee tarde). Las
   consonantes M, B, P (y V, F) piden cierre claro y retención de ~2 cuadros. Al final de una frase se mantiene la boca 2–3 cuadros en
   el silencio antes de cerrarla.
4. **Sobre «unos» y «doses».** En producción 2D limitada la boca se anima sobre doses (cada forma ≥ 2 cuadros a 24 fps) y se mezclan unos
   solo donde hace falta.
5. **Flujo:** el análisis automático hace el primer pase (Harmony: «Detect» + mapa letra→dibujo; Character Animator: toma de
   visemas editable en la línea de tiempo) y **una persona corrige**. No se acepta el automático sin revisar.
6. **Más que la boca:** la sensación de calidad viene también del movimiento secundario (cabeza, cejas) en los acentos del discurso.

## 2. Qué hace hoy nuestro motor

Rhubarb 1.14 → cues → un visema por cuadro (25 fps) → suavizado (mínimo 2 cuadros, salvo cierres A) → cambio de imagen instantáneo.
Reconocedor: `pocketSphinx` (con guion) para inglés; **`phonetic`** (genérico, sin idioma) para español y mixto.

## 3. Mediciones sobre la clase A1-M01-2 (312 s, español con ejemplos en inglés)

| Medida | Resultado | Lectura |
|---|---|---|
| Desfase boca–audio (correlación cruzada) | la energía del audio llega **+40 ms** después de abrirse la boca | Ya hay ~1 cuadro de anticipación: **el timing está bien, no tocar** |
| Cambios de forma por segundo | 5,9 (25 fps) | Cantidad razonable |
| Tramos que duran 2 cuadros | 752 de ~1.840 (≈ 41 %) | Muchas formas de solo 80 ms → aleteo |
| Saltos bruscos (apertura ≥ 0,6 en un cuadro) | 17 % de los cambios, casi todos A↔C y A↔E | Falta forma intermedia |
| Reparto de formas vs letras del guion | **D («a»): 1 % de las formas, pero la «a» es el 13 % de las letras**; A (labios cerrados): 21 %, pero b/p/m son el 7 % de las letras | **El reconocedor genérico se equivoca en español** (confunde vocales y cierres) |

La última fila es una estimación (se compara formas con letras), pero la diferencia es grande y consistente con la guía de la comunidad: el reconocedor
`phonetic` de Rhubarb es independiente del idioma y menos preciso.

## 4. Plan

**Etapa 1 — Pulido de la línea de visemas** (sin dependencias nuevas; se prueba con A/B de 30 s sobre el mismo audio):
- Forma intermedia (B/C) en los saltos bruscos A↔C/E.
- Tramos mínimos: vocales ≥ 3 cuadros; cierres M/B/P ≥ 2 cuadros; absorber lo demás.
- Mantener la boca 2–3 cuadros tras el final de cada frase antes de cerrar.
- `adelanto_ms` configurable (hoy ≈ 40 ms por el propio análisis; no subir).
- Opción 50 fps (render ×2; con 480 clases hay margen).
- Movimiento secundario: cabeceo/ceja en los picos de energía del audio.

**Etapa 2 — Identificar mejor las formas en español** (la mayor ganancia, para A1/A2 = la mitad de las clases):
- Alineación forzada con el guion (el texto es conocido). Candidatos: WhisperX (wav2vec2 por idioma), Montreal Forced Aligner (el más preciso
  de los comparados en inglés; existen modelos en español). **Cuidado con la licencia:** MMS-FA es no comercial.
- Visemas a partir de las letras (el español es casi fonético) con los tiempos del alineador.
- Complicación: A1/A2 mezclan español e inglés dentro de la clase; B1/B2 son solo inglés (ahí Rhubarb + pocketSphinx ya es lo mejor).

**Etapa 3 — Revisión ligera:** como en los estudios, revisar 3 clases de referencia por nivel en una línea de tiempo de visemas con el audio, para calibrar
parámetros globales; no revisar las 480 una por una.

**Cómo decidir:** un arnés de medición (desfase, reparto de formas vs texto, aleteo) más un video A/B de 30 s de la misma clase antes/después.

## Enlaces
- https://www.highonfilms.com/lip-sync-animation-techniques-every-character-animator-should-know/
- https://blog.cg-wire.com/the-art-of-lip-syncing-in-animated-films
- https://www.animatorisland.com/?p=3446
- https://docs.toonboom.com/help/harmony-24/premium/cut-out-animation/animate-lip-sync.html
- https://www.adobe.com/learn/adobe-character-animator/web/lip-sync-mouth-shapes
- https://github.com/DanielSWolf/rhubarb-lip-sync (README: pocketSphinx solo inglés; phonetic para otros idiomas)
- https://arxiv.org/abs/2406.19363 (comparación MFA / WhisperX / MMS en alineación forzada)
- https://aws.github.io/deep-learning-containers/whisperx/models/
- https://arxiv.org/abs/1704.08035 (visemas en español, Fernández-López y Sukno)
