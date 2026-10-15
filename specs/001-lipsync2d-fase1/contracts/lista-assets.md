# Lista de assets para producir en Higgsfield (uno por uno)

Total: **20 imágenes** (6 poses + 1 ojos + 9 bocas + 4 escenarios). Cada entrada trae el prompt
completo, listo para pegar. Marca la casilla al aceptar cada imagen. Los planos (americano,
cintura, busto, primer plano…) **no se generan**: el sistema los recorta del lienzo de la pose.

## Ajustes comunes en Higgsfield
- Generación de **imagen** (no video), **Batch 1**, **Prompt enhancement: Off**.
- Modelo: GPT Image 2.5 si aparece; si no, el de mayor resolución que acepte imagen de referencia.
- Formato PNG. Si un modelo no da transparencia real, repite con el fondo gris plano `#D0D0D0`
  (en `sdd-pose.md`, `sdd-closed-eyes.md` y `sdd-mouths.md` están las variantes de respaldo).

## Orden obligatorio
1. **Poses P1** → aceptarla (es la referencia de todo).
2. Con P1 como referencia: **ojos (07)** y **9 bocas (08 a 16)**.
3. Con P1 como referencia: **poses P2 a P6**.
4. **Escenarios** (pueden hacerse en cualquier momento; la referencia es opcional).

Hito 1 (primer video de prueba) = entradas 01, 07, 08 a 16 y 17 → **12 imágenes**.

---

## Categoría A: Poses (cuerpo)

### [ ] 01. Pose P1: Pose neutra de reposo. Es la REFERENCIA de todo lo demás.
- **Guardar como:** `entrada/P1_profesor.png`
- **Ajustes:** 16:9 · 3840×2160 · fondo transparente · referencia: Ninguna (es la primera).
- **Nota:** Si sale con fondo, usa la variante de respaldo de `sdd-pose.md` (Run B).

```
A single full-body 2D illustration of a teacher on a 16:9 canvas, for an educational class. The teacher wears glasses and a white shirt. Pose: standing, facing the camera, arms relaxed at the sides. Camera at normal height, perfectly frontal, no high angle and no low angle. Eyes open. Mouth closed in a neutral rest, lips gently together. The figure is centered, head through feet fully visible, and the body fills at least 85 percent of the canvas height, with only a small empty margin around the silhouette. Every pixel outside the character is fully transparent. Crisp edges, no colored fringe, no halo, no floor shadow, no contact shadow. Soft frontal light, neutral to slightly warm. Clean consistent line weight, flat-to-soft 2D animation style, sRGB. No text, no letters, no watermark, no logo, no extra people, no props.
```

### [ ] 02. Pose P2: Explicando con una mano.
- **Guardar como:** `entrada/P2_explica.png`
- **Ajustes:** 16:9 · 3840×2160 · fondo transparente · referencia: Adjunta **P1 aceptada**.
- **Nota:** Cara, camisa y lentes deben verse idénticos a P1; si cambian, regenera.

```
A single full-body 2D illustration of a teacher on a 16:9 canvas, for an educational class. The teacher wears glasses and a white shirt. Pose: one hand raised at chest height with the palm open, explaining, same stance and same camera. Camera at normal height, perfectly frontal, no high angle and no low angle. Eyes open. Mouth closed in a neutral rest, lips gently together. The figure is centered, head through feet fully visible, and the body fills at least 85 percent of the canvas height, with only a small empty margin around the silhouette. Every pixel outside the character is fully transparent. Crisp edges, no colored fringe, no halo, no floor shadow, no contact shadow. Soft frontal light, neutral to slightly warm. Clean consistent line weight, flat-to-soft 2D animation style, sRGB. No text, no letters, no watermark, no logo, no extra people, no props.
```

### [ ] 03. Pose P3: Gesto con las dos manos.
- **Guardar como:** `entrada/P3_manos_abiertas.png`
- **Ajustes:** 16:9 · 3840×2160 · fondo transparente · referencia: Adjunta **P1 aceptada**.
- **Nota:** Cara, camisa y lentes deben verse idénticos a P1; si cambian, regenera.

```
A single full-body 2D illustration of a teacher on a 16:9 canvas, for an educational class. The teacher wears glasses and a white shirt. Pose: both hands open in front of the body at waist height, gesturing while teaching, same stance and same camera. Camera at normal height, perfectly frontal, no high angle and no low angle. Eyes open. Mouth closed in a neutral rest, lips gently together. The figure is centered, head through feet fully visible, and the body fills at least 85 percent of the canvas height, with only a small empty margin around the silhouette. Every pixel outside the character is fully transparent. Crisp edges, no colored fringe, no halo, no floor shadow, no contact shadow. Soft frontal light, neutral to slightly warm. Clean consistent line weight, flat-to-soft 2D animation style, sRGB. No text, no letters, no watermark, no logo, no extra people, no props.
```

### [ ] 04. Pose P4: Señalando a un lado (pizarra).
- **Guardar como:** `entrada/P4_senala.png`
- **Ajustes:** 16:9 · 3840×2160 · fondo transparente · referencia: Adjunta **P1 aceptada**.
- **Nota:** Cara, camisa y lentes deben verse idénticos a P1; si cambian, regenera.

```
A single full-body 2D illustration of a teacher on a 16:9 canvas, for an educational class. The teacher wears glasses and a white shirt. Pose: one arm extended to the side, pointing toward the side of the frame, same stance and same camera. Camera at normal height, perfectly frontal, no high angle and no low angle. Eyes open. Mouth closed in a neutral rest, lips gently together. The figure is centered, head through feet fully visible, and the body fills at least 85 percent of the canvas height, with only a small empty margin around the silhouette. Every pixel outside the character is fully transparent. Crisp edges, no colored fringe, no halo, no floor shadow, no contact shadow. Soft frontal light, neutral to slightly warm. Clean consistent line weight, flat-to-soft 2D animation style, sRGB. No text, no letters, no watermark, no logo, no extra people, no props.
```

### [ ] 05. Pose P5: Pensando.
- **Guardar como:** `entrada/P5_pensando.png`
- **Ajustes:** 16:9 · 3840×2160 · fondo transparente · referencia: Adjunta **P1 aceptada**.
- **Nota:** Cara, camisa y lentes deben verse idénticos a P1; si cambian, regenera.

```
A single full-body 2D illustration of a teacher on a 16:9 canvas, for an educational class. The teacher wears glasses and a white shirt. Pose: one hand resting on the chin, thinking, the other arm relaxed, same stance and same camera. Camera at normal height, perfectly frontal, no high angle and no low angle. Eyes open. Mouth closed in a neutral rest, lips gently together. The figure is centered, head through feet fully visible, and the body fills at least 85 percent of the canvas height, with only a small empty margin around the silhouette. Every pixel outside the character is fully transparent. Crisp edges, no colored fringe, no halo, no floor shadow, no contact shadow. Soft frontal light, neutral to slightly warm. Clean consistent line weight, flat-to-soft 2D animation style, sRGB. No text, no letters, no watermark, no logo, no extra people, no props.
```

### [ ] 06. Pose P6: Brazos cruzados.
- **Guardar como:** `entrada/P6_brazos_cruzados.png`
- **Ajustes:** 16:9 · 3840×2160 · fondo transparente · referencia: Adjunta **P1 aceptada**.
- **Nota:** Cara, camisa y lentes deben verse idénticos a P1; si cambian, regenera.

```
A single full-body 2D illustration of a teacher on a 16:9 canvas, for an educational class. The teacher wears glasses and a white shirt. Pose: arms crossed in front of the chest, relaxed and friendly, same stance and same camera. Camera at normal height, perfectly frontal, no high angle and no low angle. Eyes open. Mouth closed in a neutral rest, lips gently together. The figure is centered, head through feet fully visible, and the body fills at least 85 percent of the canvas height, with only a small empty margin around the silhouette. Every pixel outside the character is fully transparent. Crisp edges, no colored fringe, no halo, no floor shadow, no contact shadow. Soft frontal light, neutral to slightly warm. Clean consistent line weight, flat-to-soft 2D animation style, sRGB. No text, no letters, no watermark, no logo, no extra people, no props.
```

---

## Categoría B: Ojos cerrados

### [ ] 07. Ojos cerrados (sirven para todas las poses con la misma cabeza)
- **Guardar como:** `entrada/P1_ojos.png`
- **Ajustes:** 2:1 · 1600×800 (mínimo 800 de ancho) · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D patch of both eyes closed. Copy the skin color, glasses, line weight, and soft frontal light from that image. Show eyelids and eyelashes, plus a margin of surrounding skin at least 15 percent around the eye region. The closed lids must be large enough to cover the open eyes of the body completely. Include the glasses frame and the lens area over the eyes, with the same reflection and the same light as the reference. The edge of the patch fades out softly, about 6 pixels of feather at a 400-pixel-wide delivery (double that fade if the image is about 800 pixels wide). Everything outside the skin patch is fully transparent. Do not draw the nose, mouth, hair, ears, or body. No text, no watermark, no logo. sRGB, clean 2D animation style.
```

---

## Categoría C: Bocas (nueve, cada una en su propia generación)

Las nueve con la **misma referencia P1**, el **mismo tamaño** 1024×640 y la boca centrada.
Si el modelo no admite tamaño personalizado, usa 3:2 y recorta las nueve con la misma ventana.

### [ ] 08. Boca A (P, B, M): labios cerrados y apretados
- **Guardar como:** `entrada/P1_boca_A.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: lips closed and pressed together, as for P, B, and M. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 09. Boca B (K, S, T, i): algo abierta, dientes juntos
- **Guardar como:** `entrada/P1_boca_B.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: slightly open with the teeth together, a small gap, as for K, S, T and the Spanish vowel i. Not a wide smile. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 10. Boca C (e (pelo)): abierta a media altura
- **Guardar como:** `entrada/P1_boca_C.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: open at mid height for the Spanish vowel e, as in the word pelo. Relaxed, not smiling, not the English ee. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 11. Boca D (a (casa)): muy abierta, la más abierta
- **Guardar como:** `entrada/P1_boca_D.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: very open, the widest of the set, for the Spanish vowel a, as in the word casa. Jaw dropped, mouth tall. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 12. Boca E (o): redondeada, abierta a media
- **Guardar como:** `entrada/P1_boca_E.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: rounded and open at mid height for the Spanish vowel o. Lips form a soft oval, not a wide smile. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 13. Boca F (u, W): labios fruncidos, círculo pequeño
- **Guardar como:** `entrada/P1_boca_F.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: lips pursed into a small circle for the Spanish vowel u and for W. The opening is small and round. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 14. Boca G (F, V): dientes superiores sobre el labio inferior
- **Guardar como:** `entrada/P1_boca_G.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: the upper teeth rest on the lower lip, as for F and V. The lower lip is slightly rolled. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 15. Boca H (L): boca abierta, lengua alta tras los dientes
- **Guardar como:** `entrada/P1_boca_H.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: mouth open with the tongue raised high behind the upper teeth, as for L. The tongue tip is visible against the upper teeth. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

### [ ] 16. Boca X (silencio): reposo: boca cerrada neutra, igual a la del cuerpo
- **Guardar como:** `entrada/P1_boca_X.png`
- **Ajustes:** 1024×640 · transparente · referencia: **P1 aceptada**

```
Using the attached pose as the only reference, draw one tight 2D mouth patch, frontal view. The center of the lips is exactly the center of the image. Include the mouth and a skin margin of at least 15 percent, with a soft alpha fade of about 12 pixels on this 1024 by 640 image. Mouth shape: neutral closed rest, lips gently together, identical to the closed mouth already on the reference body. Not pressed hard, not smiling. Copy skin color, line weight, and soft frontal light from the reference. Everything outside the skin patch is fully transparent. Do not draw eyes, glasses, nose, hair, or body. No text, no watermark, no logo.
```

---

## Categoría D: Escenarios

### [ ] 17. Escenario E1: Aula vacía con pizarra en blanco.
- **Guardar como:** `entrada/E1_aula.png`
- **Ajustes:** 16:9 · 3840×2160 · **opaco** (sin transparencia) · referencia opcional (P1, solo para la luz)
- **Nota:** Sin personas ni texto legible; el centro del suelo queda libre.

```
An empty 16:9 background plate for a 2D educational class. Scene: an empty classroom, a few desks, a blank board with no writing, open floor in the center. No people, no teacher, no characters, no silhouettes. Camera at normal eye height, frontal, no high angle and no low angle, matching a full-body teacher who will be composited later in the center. Leave the center of the floor clear. Soft frontal light, neutral to slightly warm, no strong cast shadows. Opaque image filling the whole frame, no transparency. Clean 2D illustration, same style family as a flat-to-soft classroom animation. No text, no letters, no numbers, no posters with writing, no logos, no watermark. No tiny details that would need to be read after a blur.
```

### [ ] 18. Escenario E2: Rincón de biblioteca.
- **Guardar como:** `entrada/E2_biblioteca.png`
- **Ajustes:** 16:9 · 3840×2160 · **opaco** (sin transparencia) · referencia opcional (P1, solo para la luz)
- **Nota:** Sin personas ni texto legible; el centro del suelo queda libre.

```
An empty 16:9 background plate for a 2D educational class. Scene: an empty library corner with shelves and a clear floor in the center, no book spines readable. No people, no teacher, no characters, no silhouettes. Camera at normal eye height, frontal, no high angle and no low angle, matching a full-body teacher who will be composited later in the center. Leave the center of the floor clear. Soft frontal light, neutral to slightly warm, no strong cast shadows. Opaque image filling the whole frame, no transparency. Clean 2D illustration, same style family as a flat-to-soft classroom animation. No text, no letters, no numbers, no posters with writing, no logos, no watermark. No tiny details that would need to be read after a blur.
```

### [ ] 19. Escenario E3: Laboratorio de ciencias.
- **Guardar como:** `entrada/E3_laboratorio.png`
- **Ajustes:** 16:9 · 3840×2160 · **opaco** (sin transparencia) · referencia opcional (P1, solo para la luz)
- **Nota:** Sin personas ni texto legible; el centro del suelo queda libre.

```
An empty 16:9 background plate for a 2D educational class. Scene: an empty science laboratory with benches along the walls and a clear floor in the center, no labels or writing anywhere. No people, no teacher, no characters, no silhouettes. Camera at normal eye height, frontal, no high angle and no low angle, matching a full-body teacher who will be composited later in the center. Leave the center of the floor clear. Soft frontal light, neutral to slightly warm, no strong cast shadows. Opaque image filling the whole frame, no transparency. Clean 2D illustration, same style family as a flat-to-soft classroom animation. No text, no letters, no numbers, no posters with writing, no logos, no watermark. No tiny details that would need to be read after a blur.
```

### [ ] 20. Escenario E4: Estudio con estantería.
- **Guardar como:** `entrada/E4_estudio.png`
- **Ajustes:** 16:9 · 3840×2160 · **opaco** (sin transparencia) · referencia opcional (P1, solo para la luz)
- **Nota:** Sin personas ni texto legible; el centro del suelo queda libre.

```
An empty 16:9 background plate for a 2D educational class. Scene: a warm home study with a bookcase and a plain wall, a clear floor in the center, no readable titles or writing. No people, no teacher, no characters, no silhouettes. Camera at normal eye height, frontal, no high angle and no low angle, matching a full-body teacher who will be composited later in the center. Leave the center of the floor clear. Soft frontal light, neutral to slightly warm, no strong cast shadows. Opaque image filling the whole frame, no transparency. Clean 2D illustration, same style family as a flat-to-soft classroom animation. No text, no letters, no numbers, no posters with writing, no logos, no watermark. No tiny details that would need to be read after a blur.
```

---

## Lista de comprobación final
- [ ] 6 poses P1 a P6 con la misma cara, camisa, lentes y luz.
- [ ] 1 imagen de ojos que tapa por completo los ojos abiertos de P1.
- [ ] 9 bocas del mismo tamaño, centradas, con X igual a la boca cerrada de P1.
- [ ] 4 escenarios opacos, sin personas ni texto.
- [ ] Todo con los nombres de la columna «Guardar como», dentro de `entrada/`.

## Notas
- Las poses P2 a P6 reutilizan los ojos y las bocas de P1 (`bocas_de: P1`) porque la cabeza es la
  misma, frontal. Si en alguna pose la cabeza queda claramente distinta (más grande, girada), 
  necesitará su propio juego de ojos y bocas.
- Para producir más variedad después, solo hay que añadir poses o escenarios con el siguiente número.
- Un ángulo de cámara distinto (picado, contrapicado…) es **otra pose** con su propia cabeza.
