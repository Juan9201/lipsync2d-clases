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

## Editor de poses (vigente: bocas y parpadeo, frontal y 3/4)

`editor/editor.html` reúne el calibrador de bocas por forma y la prueba del parpadeo para las dos vistas.
Para abrirlo: pulsa «editor-poses» en el panel de servidores de la app (o `python -m http.server 8770 --directory prototipos`)
y entra en `http://localhost:8770/editor/editor.html`.
Las imágenes del editor se generan con `.venv\Scripts\python.exe -I prototipos\editor\construir_editor.py`
(no se versionan). Descarga la calibración de cada vista con «Descargar calibración de esta vista» y se importa con
`python -m src.biblioteca importar-poses --origen <poses> --calibraciones <json> --bocas <vista>=<carpeta de bocas>`.
