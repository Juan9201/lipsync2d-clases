# Prototipos (referencia, no es el sistema final)

Todo lo de esta carpeta nació en las pruebas del 14 y 15 de octubre de 2026 para decidir el diseño de la spec v3.

- `calibradores/`: herramientas HTML para calibrar bocas por forma (`Calibrador4` es la vigente, 3/4), colocar el juego de
  bocas en una escena (`Calibrador3`) y generar prompts para Higgsfield (`Generador`). Se abren con un servidor local
  (`python -m http.server` dentro de la carpeta) porque cargan imágenes. Las **calibraciones de las 11 poses 3/4** están en
  `calibradores/Calibrador4/calibraciones_34_todas_v3.json`.
- `bocas/`: juego frontal y juego 3/4 elegidos (hoja original incluida).
- `scripts_de_prueba/`: scripts que renderizaron los videos de prueba. **Usan rutas absolutas de esta PC y módulos temporales**;
  se conservan como referencia para las tareas T091 a T106 de `specs/001-lipsync2d-fase1/tasks.md`.

**No versionado** (demasiado pesado; hay que respaldarlo aparte): las 43 poses y sus parpadeos
(`Temp Real Assest Testing/Torso Organizado/`), los originales de Higgsfield, los videos de prueba y `BG 01.mp4`.
