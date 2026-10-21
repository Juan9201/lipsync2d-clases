# 00 · Estilo común y método (léelo primero)

Los cinco escenarios (`01_aula`, `02_casa`, `03_oficina`, `04_calle`, `05_tienda_cafe`) usan **este mismo bloque de estilo**.
Pégalo **al principio de cada prompt**, antes del texto de la escena. Así los cinco quedan con el mismo dibujo que el profesor.

## Bloque de estilo (pegar tal cual, en inglés)

```
2D cel-shaded illustration in the style of a modern western animated series / graphic novel. Clean medium-weight dark ink
outlines around every object, flat colors with soft two-tone shading and subtle highlights, slightly hand-painted texture.
Natural saturated but not neon colors, bright soft daylight, gentle ambient occlusion. NOT photorealistic, NOT 3D render,
NO glow effects, NO neon, NO blurry photo background. No people, no animals, no readable text, no logos (use abstract
scribbles or blank surfaces wherever text would go). 16:9 landscape, 3840x2160, camera at chest height, slight depth.
```

Por qué: el profesor es una ilustración con contorno negro y colores planos con sombra suave. Los fondos que tenías
(`Fondo 01 Back/Front`) eran oscuros y brillantes: no combinan. Todo nuevo debe ser **luminoso, de día y con contorno**.

## Composición (muy importante para que el profesor quede bien)

El profesor aparece **de la cintura hacia arriba, en la mitad derecha** del cuadro (cabeza hacia el 70 % del ancho y el 28 % del alto).
- **Mitad derecha, parte media:** zona tranquila, sin objetos altos ni mucho contraste. Ahí va él.
- **Izquierda y bordes:** aquí va el detalle y lo que da personalidad al lugar.
- **Parte baja:** lo que queda delante de su cintura (mesa, mostrador, banco…) es la capa **FRENTE**.
- Luz: una dirección clara (por ejemplo ventana a la izquierda). Anótala: el editor de escenas la usa para sombrear al profesor.

## Las 3 piezas de cada escenario

| Pieza | Qué es | Archivo que guardas |
|---|---|---|
| **BACK (fondo)** | Todo lo que está *detrás* del profesor: pared, ventanas, muebles del fondo, suelo. Sin mesa delante. | `<escena>_back.png` |
| **FRONT (frente)** | Solo lo que está *delante* de su cintura (mesa/mostrador/muro bajo/banco) con **transparencia**. Mismo tamaño y misma cámara. | `<escena>_front.png` |
| **Profesor** | Lo coloco yo con el *Editor de escenas* y tú apruebas el encuadre. | — |

## Método recomendado (3 pasos, para que BACK y FRONT encajen píxel a píxel)

1. **Escena completa:** genera la imagen con el bloque de estilo + el prompt «ESCENA COMPLETA» del archivo de cada escenario. Elige la mejor.
2. **BACK:** con esa imagen como referencia, edítala: *«Remove the <mesa/mostrador…> and everything in the foreground; fill in the floor and wall behind it plausibly. Keep everything else exactly identical (same camera, same colors, same objects).»*
3. **FRONT:** con la misma imagen de referencia: *«Keep ONLY the <mesa/mostrador…> and its props on a solid pure green (#00FF00) background. Do not change its size, position or colors.»* Quita el verde (cualquier quita-fondos) y guarda **PNG con transparencia**.

Comprobación: ponlas una sobre otra al 50 % en cualquier editor. Los bordes deben coincidir; si el frente se movió un poco, repite el paso 3. Si hay una pequeña diferencia, el editor de escenas la deja ver (se vería un doble borde).

## Cómo subirlas
En la interfaz: **Escenarios → subir el fondo (BACK)** y luego **Subir frente (FRONT)**. Después me avisas y coloco al profesor.

## Lista de comprobación (cada escenario)
- [ ] Mismo estilo que el profesor (contorno, colores planos, luz de día; nada de neón).
- [ ] 3840×2160 (o al menos 1920×1080), BACK y FRONT del **mismo tamaño**.
- [ ] Sin texto legible ni personas.
- [ ] Zona derecha-media despejada.
- [ ] FRONT con transparencia real (comprueba que el fondo se ve a cuadros en tu editor).

## Orden sugerido (para no gastar créditos de más)
Empieza **solo por el aula**, sube la imagen y la reviso contra el profesor. Si el estilo casa, haces los otros cuatro.
