# V3 parpadeo (frontal) · descargada del editor el 2026-10-24 07:15

Es la calibración que el usuario descargó con «Descargar calibración de esta vista».

- Parpadeo: cerrado `Frontal_Blink_Full.png` desp [0, -10]; medio `Frontal_Blink_Middle.png` desp [0, -4]; borde 10 px (igual que la V2 de las 07:05).
- Único recuadro de ojos distinto de la V2: `frontal_bienvenida_01` = [1675, 139, 474, 502] (V2: [1674, 308, 476, 164]).
- **No importar las bocas de este archivo.** En `frontal_bienvenida_01` la boca viene espejada y desplazada (X.x = 2102; lo guardado y lo que usa el render es 1910). Fue un cambio en la sesión del editor, no está en disco. Las bocas de las otras 31 poses coinciden con las del render.
- Para importar solo el parpadeo, usar las bocas que cada pose ya tiene (como en las pruebas de `salidas/prueba_parpadeo/`).
