# Guía de assets: qué producir con la IA, en qué formato y con qué medidas exactas

README de assets (FR-065). Carpeta de entrada: `entrada/` (suelta ahí los archivos con los nombres
de la sección 8 y ejecuta `python -m src.biblioteca importar`).

Todas las medidas salen de cómo trabaja el sistema: el video final es **1280×720** y cada plano es
un recorte (zoom) del lienzo de la pose. Cuanto más grande es el lienzo, más nítidos quedan los
planos cerrados. **Versión del documento: 2026-10-14.**

---

## 0. Medidas exactas (la tabla que necesitas tener a mano)

| Pieza | Archivo | Tamaño recomendado | Mínimo aceptable | Formato | Fondo |
|---|---|---|---|---|---|
| **Pose** (personaje en su lienzo) | `P#_nombre.png` | **3840 × 2160 px** (16:9) | 2560 × 1440 px | PNG RGBA 8 bits | **Transparente** |
| **Escenario** (solo el fondo) | `E#_nombre.png` o `.jpg` | **3840 × 2160 px** (16:9) | 2560 × 1440 px | PNG, o JPG calidad ≥ 92 | Opaco, **sin personaje** |
| **Ojos cerrados** | `P#_ojos.png` | **640 × 256 px** (5:2) | 400 × 160 px | PNG RGBA 8 bits | Transparente |
| **Boca** (nueve archivos iguales) | `P#_boca_A.png` … `P#_boca_X.png` | **512 × 320 px** (8:5) | 256 × 160 px | PNG RGBA 8 bits | Transparente |

- Espacio de color **sRGB**, 8 bits por canal, sin marcas de agua ni texto incrustado.
- Los 9 archivos de boca de una pose tienen que medir **exactamente lo mismo** (el sistema lo exige).
- Si vas a usar mucho los planos `PL5` y `PL6` (primer plano y primerísimo primer plano), sube las
  bocas a **768 × 480 px** y los ojos a **960 × 384 px**.
- Un PNG de 3840 × 2160 con transparencia pesa entre 8 y 20 MB: es normal.

### Lo que ya tienes, medido
| Archivo | Medida real | Qué significa |
|---|---|---|
| `P1_profesor.png` | **2048 × 1152 px**, RGBA (sin transparencia real) | Sirve hasta `PL3` nítido y `PL4` un poco suave. Para planos más cerrados conviene 3840 × 2160. |
| `07_pose_presentando.png` | **425 × 783 px**, RGB (sin canal alfa, fondo blanco) | Es demasiado pequeña: dentro de un lienzo de 3840 × 2160 el personaje mediría 783 px de alto y habría que ampliarlo 2,3 veces. **Hay que regenerarla** a 3840 × 2160 con el personaje de ≥ 1836 px de alto. |

---

## 1. Planos fotográficos: cuánto recorta el sistema de tu lienzo

El plano es la ventana que se recorta del lienzo de la pose (siempre 16:9) y se lleva a 1280 × 720.
La cabeza queda centrada horizontalmente y a un tercio (33 %) de la altura de la ventana.

| Plano | Código | Ventana (% del alto) | Ventana a 3840×2160 | Ventana a 2560×1440 | Ventana a 2048×1152 | Qué debe verse |
|---|---|---|---|---|---|---|
| Entero | PL1 | 100 % | 3840 × 2160 | 2560 × 1440 | 2048 × 1152 | De la cabeza a los pies |
| Americano | PL2 | 75 % | 2880 × 1620 | 1920 × 1080 | 1536 × 864 | Cabeza hasta las rodillas |
| Cintura | PL3 | 58 % | 2228 × 1253 | 1484 × 835 | 1188 × 668 | Cabeza hasta la cintura |
| Busto | PL4 | 42 % | 1612 × 907 | 1076 × 605 | 860 × 484 | Cabeza y pecho |
| Primer plano | PL5 | 30 % | 1152 × 648 | 768 × 432 | 615 × 346 | Cabeza y hombros |
| Primerísimo primer plano | PL6 | 18 % | 692 × 389 | 460 × 259 | 368 × 207 | Del entrecejo a la barbilla |

**Nitidez** (la ventana tiene que tener **720 px de alto o más** para no ampliarse):

| Lienzo | PL1 | PL2 | PL3 | PL4 | PL5 | PL6 |
|---|---|---|---|---|---|---|
| **3840 × 2160** | nítido | nítido | nítido | nítido | casi (amplía 1,1×) | suave (amplía 1,9×) |
| 2560 × 1440 | nítido | nítido | nítido | suave (1,2×) | suave (1,7×) | borroso (2,8×) |
| 2048 × 1152 | nítido | nítido | casi (1,1×) | suave (1,5×) | borroso (2,1×) | borroso (3,5×) |

Recomendación: **3840 × 2160** y usar sobre todo de `PL2` a `PL4`. Para un `PL6` realmente nítido
haría falta un lienzo de 7111 × 4000, que ningún generador entrega; úsalo con moderación.

**Dónde colocar la cabeza para que cada plano la deje centrada** (como fracción del lienzo; fuera de
este rango la ventana se desplaza y la cabeza queda descentrada, sin romperse nada):

| Plano | Centro de la cabeza en X | Centro de la cabeza en Y |
|---|---|---|
| PL2 | entre 37,5 % y 62,5 % | entre 24,8 % y 49,8 % |
| PL3 | entre 29 % y 71 % | entre 19,1 % y 61,1 % |
| PL4 | entre 21 % y 79 % | entre 13,9 % y 71,9 % |
| PL5 | entre 15 % y 85 % | entre 9,9 % y 79,9 % |
| PL6 | entre 9 % y 91 % | entre 5,9 % y 87,9 % |

Ejemplo con tu `P1` (cabeza en x ≈ 74 %, y ≈ 25 %): en `PL4` y `PL5` queda centrada; en `PL2` y `PL3` la
ventana se desplaza a la derecha y la cabeza queda algo descentrada. Si quieres tomas más
equilibradas, coloca al personaje más cerca del centro (x entre 40 % y 60 %).

---

## 2. Pose (cuerpo)
- **Lienzo 3840 × 2160** con el personaje **ya colocado donde aparecerá** en el encuadre más abierto
  (`PL1`). Todo lo demás, transparente.
- **Tamaño del personaje en el lienzo:**
  - Cuerpo entero: ≥ 85 % del alto → **≥ 1836 px** de la cabeza a los pies.
  - Si el personaje sale cortado (como tu `P1`, de la cabeza a los muslos): la **cabeza debe medir
    ≥ 12 % del alto → ≥ 260 px** (en `P1`, escalada a 3840 × 2160, mide unos 345 px).
- Cámara a **altura normal** (frontal, sin picado ni contrapicado). Un ángulo distinto es **otra pose**.
- **Ojos abiertos y boca cerrada en reposo** (la forma `X`). El sistema pone encima las bocas y los
  ojos cerrados. (Tu `P1` tiene la boca abierta: por eso asoma detrás de las bocas de prueba.
  Genera la pose con la boca cerrada.)
- Bordes limpios: sin halo del fondo original ni sombra proyectada en el suelo (si la quieres, va en
  el escenario).
- **Misma luz, misma ropa, mismo estilo y mismo logo en todas las poses.**
- **Si la IA no da transparencia:** entrega el personaje sobre un **color plano uniforme** (gris claro
  o verde sin sombras ni degradado) o con su fondo; el sistema lo separa (BiRefNet) y puedes corregir
  la máscara a mano.

## 3. Ojos cerrados (con gafas o sin gafas)
- **640 × 256 px**, fondo transparente. Cubre **ambos ojos** cerrados con párpados y pestañas.
- Debe medir en el lienzo ≈ **55–62 % del ancho de la cabeza** (en `P1`: 100 px de 170 px, a 3840 × 2160:
  unos 188 px) y **tapar por completo** los ojos abiertos del cuerpo. El archivo es más grande que
  eso a propósito: el sistema lo reduce, y reducir queda nítido.
- Margen de piel ≥ 15 % alrededor, con borde suave (degradado de ≈ 8 px a 640 px de ancho).
- **Cada look necesita sus propios ojos.** Con gafas: incluye la montura y el cristal con el mismo
  reflejo y luz que el cuerpo. Sin gafas: solo párpados. Trata «con gafas» y «sin gafas» como **poses
  distintas**; las bocas se pueden compartir (`bocas_de`) y, si dos poses tienen la misma cara y las
  mismas gafas, los ojos también (`ojos_de`).

## 4. Bocas (nueve archivos del mismo tamaño)
- **512 × 320 px** cada una, fondo transparente, **boca centrada**: el centro de la boca es el centro
  de la imagen en las nueve.
- Ancho de la boca en el lienzo ≈ **38–42 % del ancho de la cabeza** (en `P1`: 70 px de 170 px; a
  3840 × 2160, unos 131 px). El archivo la trae más grande: el sistema la reduce.
- Cada imagen incluye la boca **más un margen de piel de ≥ 15 %** con borde suave (≈ 8 px), para cubrir
  la boca cerrada del cuerpo y fundirse sin costura.
- Misma luz, mismo grosor de línea y mismo color de piel que el cuerpo. **Misma perspectiva e
  inclinación que la cabeza de la pose** (si la cabeza está girada o inclinada, dibuja las bocas así;
  el sistema solo permite un giro menor en la calibración).

| Visema | Cuándo suena | Cómo dibujarla |
|---|---|---|
| **A** | P, B, M | Labios **cerrados y apretados** |
| **B** | K, S, T, «i» | Boca **algo abierta, dientes juntos** |
| **C** | «e» (como en *pelo*) | Boca **abierta a media altura** |
| **D** | «a» (como en *casa*) | Boca **muy abierta** (la más abierta) |
| **E** | «o» | Boca **redondeada, abierta a media** |
| **F** | «u», W | Labios **fruncidos, círculo pequeño** |
| **G** | F, V | **Dientes superiores sobre el labio inferior** |
| **H** | L | Boca abierta con la **lengua alta tras los dientes de arriba** |
| **X** | silencio | **Reposo**: boca cerrada neutra (igual a la boca del cuerpo) |

Tamaño con el que se verán en el video (a 1280 × 720, boca de 131 px en un lienzo de 3840 × 2160):
`PL1` 44 px · `PL2` 58 px · `PL3` 75 px · `PL4` 104 px · `PL5` 146 px · `PL6` 243 px de ancho.
Los 512 px del archivo cubren incluso `PL6` sin ampliar.

## 5. Escenario (solo el fondo)
- **3840 × 2160 px**, opaco, **sin personaje**.
- **La misma cámara que las poses:** altura normal, misma perspectiva y misma línea del horizonte.
- **Deja libre la zona donde estará el personaje.** Si el personaje de la pose va en el tercio derecho,
  esa zona del escenario debe ser pared o suelo libre, sin muebles ni objetos.
- Luz coherente con las poses (dirección y temperatura de color).
- Los planos cerrados amplían y **desenfocan** el fondo (σ de 0, 1, 2, 4, 6 y 9 px de `PL1` a `PL6`):
  evita texto pequeño que se deba leer en primer plano.
- Pesa unos 5–15 MB en PNG; el JPG (calidad ≥ 92) sirve y pesa menos.

## 6. Composición: cómo encaja todo (resumen visual)
```
Lienzo 3840 × 2160 (pose, transparente)          Escenario 3840 × 2160 (opaco)
┌──────────────────────────────┐                 ┌──────────────────────────────┐
│                  ┌──┐        │                 │  fondo sin personaje         │
│                  │◉ │ cabeza │   se superpone  │  con la zona del personaje   │
│                  ├──┤        │      ───►       │  libre                       │
│                  │  │ cuerpo │                 │                              │
└──────────────────────────────┘                 └──────────────────────────────┘
       ▼ el plano recorta la MISMA ventana de los dos y la lleva a 1280 × 720 ▼
```

## 7. Cambios de toma que se ven naturales (guía de continuidad)
1. Cambia **una cosa a la vez**: o el plano o la pose, no ambos.
2. Salta al menos **un paso de plano** (de `PL2` a `PL4` sí; de `PL4` a otro `PL4` no).
3. Dentro de un escenario, alterna abiertos y cerrados: abierto → cerrado → abierto.
4. No repitas la misma pose seguida.
5. Misma luz, ropa, estilo y logo en todas las tomas.
6. Evita cortes cada pocos segundos: 8–30 s por toma se siente natural en una clase.

## 8. Nombres para soltar en `entrada/`
```
P3_explicando.png                 ← pose (3840 × 2160, transparente)
P3_ojos.png                       ← ojos cerrados (640 × 256)
P3_boca_A.png ... P3_boca_X.png   ← las nueve bocas (512 × 320, todas iguales)
E2_salon.png                      ← escenario (3840 × 2160)
```
Poses que comparten cabeza (solo cambian los brazos) pueden reutilizar bocas: omite sus
`P#_boca_*` e indica `bocas_de: P1`. Con la misma cara y las mismas gafas, también `ojos_de`.

## 9. Pedidos listos para pegar a la IA que genera las imágenes
**Pose.** «Genera al mismo personaje de la imagen de referencia, de frente y a la altura de cámara
normal, en un lienzo 16:9 de 3840×2160 px con fondo transparente. Debe medir al menos 1836 px de alto
(o la cabeza ≥ 260 px si sale cortado), ojos abiertos, boca cerrada neutra, sin sombra en el suelo, con
la misma luz, ropa, logo y estilo que la referencia.»

**Boca.** «Toma la cabeza de la imagen de referencia y dibuja SOLO la boca, centrada, en una imagen de
512×320 px con fondo transparente, con un margen de piel del 15 % alrededor y bordes suaves, misma luz
y misma inclinación de la cabeza. Hazme nueve versiones: A labios cerrados apretados; B boca algo abierta
con los dientes juntos; C abierta a media altura; D muy abierta; E redondeada a media; F labios fruncidos
en círculo pequeño; G dientes superiores sobre el labio inferior; H abierta con la lengua alta; X reposo,
boca cerrada neutra.»

**Ojos cerrados.** «Dibuja los dos ojos cerrados del personaje (con [gafas / sin gafas]) en una imagen de
640×256 px con fondo transparente: párpados y pestañas, margen de piel del 15 % con bordes suaves, misma
luz y misma inclinación que la cabeza de la referencia.»

**Escenario.** «Genera [descripción del lugar], vista frontal a la altura de cámara normal, 16:9 de
3840×2160 px, sin personas, con la zona del [tercio derecho] despejada, luz [dirección y color] y sin
texto pequeño.»

## 10. Consejos para mantener la coherencia
- Genera **P1 primero** y las demás poses **con P1 como imagen de referencia**.
- Para las bocas y los ojos, pide **la misma cabeza de P1**, con la misma inclinación, cambiando solo la
  boca o los ojos, y recorta después.
- Si tu generador entrega 2048 × 1152 (como `P1`), amplía a 3840 × 2160 con **Real-ESRGAN** (gratuito y
  local). Todavía no está integrado en el proyecto; si lo necesitas lo añadimos como paso de preparación.
- Revisa que cada boca, puesta sobre el cuerpo, **no deje un borde visible** y que los ojos cerrados
  tapen del todo los abiertos.

## 11. Kit mínimo para probar el sistema con varias tomas (US4)
| Qué | Cuántos | Medidas |
|---|---|---|
| Pose nueva (distinta de `P1`) | 1 | 3840 × 2160, transparente, boca cerrada |
| Ojos cerrados de esa pose | 1 | 640 × 256 |
| Bocas de esa pose (o `bocas_de: P1` si la cabeza es igual) | 9 | 512 × 320 |
| Escenarios | 1 a 2 | 3840 × 2160, sin personaje |
Para producir las 7.632 clases hace falta además **la biblioteca definitiva** (todas las poses y
escenarios que quieras variar): conviene fijar el estilo con el kit mínimo antes de generarlo todo.

## 12. Lista de comprobación (la valida el sistema, FR-061)
- [ ] Nombres correctos (`P#_...`, `E#_...`).
- [ ] Pose: PNG con transparencia, lienzo 16:9 (ideal 3840 × 2160), personaje ≥ 85 % del alto.
- [ ] 9 bocas, **todas del mismo tamaño**, PNG con transparencia (ideal 512 × 320).
- [ ] Ojos cerrados: PNG con transparencia (ideal 640 × 256), propios de cada look (con o sin gafas).
- [ ] Escenario: 16:9 (ideal 3840 × 2160), sin personaje, zona del personaje libre.
