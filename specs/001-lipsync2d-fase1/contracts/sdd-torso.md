# Specification: Torso variants with a frozen head

**Status:** Ready for Higgsfield execution
**Feature:** `001-lipsync2d-fase1`
**Parent:** `spec.md` (approved v2), pose library (FR-050). Trace: FR-065, FR-054, FR-090.
**Depends on:** the approved master pose (transparent PNG, mouthless face). Attach it as the reference.

## 1. Goal

Generate many body poses (gestures) that share **exactly the same head**, so the pipeline can swap poses
during a class without the head jumping and so one mouth calibration serves every pose.

## 2. Acceptance scenarios

1. **Given** a generated pose and the master pose, **when** the head regions are compared, **then** hair, ears, glasses,
   eyes, eyebrows, nose, skin and the mouthless lower face are identical in position, size and angle.
2. **Given** any generated pose, **when** the face is inspected, **then** there is still no mouth, no lips, no mustache, no goatee.
3. **Given** the generated pose, **when** the canvas is measured, **then** it has the same size as the master and a transparent background.
4. **Given** the generated pose, **when** hands and arms are inspected, **then** none overlaps the head or covers the face.
5. **Given** the neck and shoulders, **when** they are inspected, **then** the neck joins the frozen head without a visible seam.

## 3. Higgsfield execution

Run **image edit** (not text to image, not video). One image per run. Prompt enhancement off.

| Control | Set to |
|---|---|
| Model | GPT Image 2.5 if listed; otherwise the highest-resolution image-edit model that accepts a reference |
| Reference | The master pose (`personaje_sin_fondo_sin_boca.png`). Optional: the head mask `mascara_proteger_cabeza.png` if the tool supports inpainting masks (white = protected head) |
| Size | Same as the master (2000×1125 or 3840×2160) |
| Background | `transparent`, output PNG |
| Batch | 1 |

Replace `POSE_ACTION` and paste **one** prompt:

```
Edit the attached image. It is a 2D comic teacher on a transparent 16:9 canvas.

FREEZE THE HEAD. Everything from the top of the hair down to the bottom of the chin must stay exactly as in the attached image, pixel for pixel: same position, same size, same angle, same hair, ears, glasses, eyebrows, eyes, nose, skin color, shading and outline, and the same smooth mouthless lower face. Do not move, rotate, scale, redraw, restyle, relight or sharpen the head. Do not add a mouth, lips, mustache or goatee. The head is locked and immovable.

CHANGE ONLY THE BODY BELOW THE CHIN: the neck, shoulders, torso, arms, hands and the posture of the shirt. New body pose: POSE_ACTION.

Keep the same character and clothes: white shirt with the same green and blue logo, black belt, dark gray trousers. Keep the same line weight, colors and soft frontal light. The shoulders stay at a believable height directly under the locked head, and the neck joins the head without a seam. No hand or arm may overlap, touch or cover the head or face. Camera frontal at normal height, no perspective change.

Keep the exact same canvas size. Everything outside the character is fully transparent (alpha 0): no background, no floor shadow, no halo, crisp edges. No extra text besides the existing logo, no watermark, no extra people, no new props unless the pose says so.
```

### POSE_ACTION library

| ID | Type | `POSE_ACTION` |
|---|---|---|
| neutro | state | `standing relaxed, both arms down at the sides` |
| explicar | state | `both hands open in front of the waist, palms up, explaining` |
| pulgar | accent | `one hand giving a thumbs up at shoulder height, the other arm relaxed` |
| señalar | accent | `one arm extended to the side pointing with the index finger, the other arm relaxed` |
| bienvenida | accent | `both arms open wide at the sides, welcoming, palms forward` |
| pregunta | state | `one hand raised at chest height with the palm up, as if asking a question, the other arm relaxed` |
| contar | accent | `one hand raised at chest height showing three fingers, the other arm relaxed` |
| libreta | state | `holding a black notebook against the chest with both hands` |

## 4. Quality gate (automatic, my side)

After generation the head is compared with the master. If it moved or scaled, the generated image is registered back
onto the master (translation and scale) and the original head is pasted over it with a feathered seam at the neck, so
the head is guaranteed identical.
