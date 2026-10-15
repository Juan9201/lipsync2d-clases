# Prompt de Higgsfield para las bocas (IA especializada en assets de animación)

Objetivo: que una IA de imágenes actúe **solo** como dibujante de estudio de animación 2D y entregue
las nueve bocas de lipsync (A, B, C, D, E, F, G, H, X) en el estilo del personaje.

Estado: borrador de trabajo derivado de las pruebas del 2026-10-14. **Sustituye a `sdd-mouths.md`
cuando el usuario lo apruebe** (bocas solo labios, sin bigote ni chiva, sobre pose sin boca).

---

## 1. Referencias que se adjuntan (orden fijo)

| # | Imagen | Para qué sirve |
|---|---|---|
| Ref 1 | Recorte de la **cara de la pose sin boca** (frontal), a tamaño grande | Grosor de línea, color de contorno, paleta, nivel de simplificación, proporción de la cara |
| Ref 2 | Una **hoja de bocas de muestra** (p. ej. `Cartoon\` o la hoja 3×6) | Vocabulario de formas y estilo de dibujo de las bocas |

Si el producto solo admite una referencia, adjunta Ref 1 y pega en el prompt la frase de estilo de la sección 3.

## 2. Ajustes en Higgsfield
- Generación de **imagen**, no video. **Prompt enhancement: Off**.
- Formato **1:1** (cuadrado) o el más grande disponible, **≥ 3000 px** por lado; PNG.
- **Batch 4** si existe: se elige la mejor lámina. Si no, 1.
- Fondo: **blanco plano** (más fiable que pedir transparencia; el recorte lo hace mi script).
- Modelo: GPT Image 2.5 si aparece; si no, el de mayor resolución que admita 2 imágenes de referencia.

## 3. PROMPT A, la lámina completa (pégalo tal cual)

```
ROLE
You are a senior studio 2D character animator and cut-out rigging artist. Your only job is to produce clean, production-ready lip-sync mouth assets for a 2D talking-head character. You do not make illustrations, portraits, scenes or concept art. You work like a studio mouth chart: every mouth is a separate flat drawing, frontal, perfectly symmetrical, built to be cut out and swapped frame by frame. Consistency beats creativity: all mouths share the same line weight, colors, scale logic and center.

REFERENCES
Reference image 1 is the character's face: copy from it the outline color, the line weight, the flat color palette and the level of simplification of the drawing. Reference image 2 is a mouth sample: take the shape vocabulary and drawing style from it, but redraw every mouth frontal and symmetrical.

TASK
Draw ONE mouth chart: nine frontal mouth shapes in a 3 by 3 grid on a pure flat white background, equal cells, each mouth centered in its cell with a wide empty margin, no overlaps, no labels, no numbers, no text. Reading order is left to right, top to bottom:
1 A: closed, lips pressed together, a short straight line with a slight lower lip, as for the sounds P, B, M.
2 B: slightly open, teeth together, a thin gap, as for K, S, T and the vowel EE. Not a wide smile.
3 C: open at mid height, relaxed, as for the vowel EH. Not smiling.
4 D: widest opening, jaw dropped, as for the vowel AH. The most open of the nine.
5 E: rounded, open at mid height, as for the vowel OH. A soft oval.
6 F: small pursed circle, lips pushed forward, as for OO and W. The smallest opening.
7 G: upper teeth resting on the lower lip, as for F and V.
8 H: mouth open with the tongue raised behind the upper teeth, as for L.
9 X: relaxed neutral rest, mouth closed, softer than A. Straight line, level corners.

CONSISTENCY RULES
Same line weight and outline color on all nine. Same flat colors: white teeth, a single flat red-pink for the tongue, dark mouth interior. Opening size grows from A to D in proportion; widths stay similar, heights change. Every mouth is built around the same horizontal center line, with the upper lip line at the same height in all nine cells so they can be swapped without jumping. The corners of the mouth are level, neither a smile nor a frown, except where the shape itself requires it. A thin soft light-gray crescent shadow under the lower lip is allowed, the same on all nine.

DO NOT DRAW
No mustache, no goatee, no beard, no nose, no cheeks, no chin, no head, no skin, no face outline, no teeth outline detail beyond simple clean shapes. No photorealism, no 3D render, no airbrushed gradients, no glossy highlights, no texture, no hair-by-hair detail. No scribbles inside the shapes. No text, no letters, no watermark, no logo.
```

## 4. PROMPT B, corregir una sola boca (si una sale mal)
Adjunta la lámina aceptada como referencia y la cara de la pose. Reemplaza `VISEMA` y `FORMA`.

```
ROLE
You are a senior studio 2D animator producing lip-sync mouth assets only.

Using the attached chart as the style reference and the attached face for line weight and colors, redraw ONE mouth, frontal and symmetrical, centered on a pure flat white background with a wide empty margin. Same line weight, outline color, flat colors and level of simplification as the chart. The upper lip line sits where it sits in the chart. Mouth: VISEMA. Shape: FORMA. Draw only the lips, teeth and tongue: no mustache, no goatee, no nose, no skin, no face. No gradients, no gloss, no text, no watermark.
```

| VISEMA | FORMA |
|---|---|
| G | the upper teeth rest on the lower lip, lower lip slightly rolled, as for F and V; level corners, not a frown |
| F | a small round pursed opening, lips pushed forward, the smallest opening of the set |
| E | a soft oval opening at mid height, lips rounded |
| H | open mouth with the tongue tip raised behind the upper teeth |
| X | closed neutral rest, a straight line with level corners, softer than A |

## 5. Qué se hace con el resultado
1. Eliges la mejor lámina (de las 4).
2. Me la pasas: la recorto en 9 PNG con transparencia, las centro y las alineo (mismo código que en las pruebas).
3. Compongo un video corto con tu audio real y lo revisas.
4. Las bocas que fallen se rehacen con el PROMPT B.

## 6. Lista de comprobación de la lámina
- [ ] Nueve formas, sin etiquetas ni texto.
- [ ] Frontales y simétricas; las esquinas a nivel (ni sonrisa ni ceño).
- [ ] D la más abierta; F el círculo más pequeño; A y X cerradas.
- [ ] G con dientes superiores sobre el labio inferior; H con la lengua arriba.
- [ ] Mismo grosor de línea y mismos colores en las nueve; sin degradados.
- [ ] Sin bigote, chiva, nariz ni piel.
