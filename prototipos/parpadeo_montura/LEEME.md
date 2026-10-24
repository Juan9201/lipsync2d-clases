# Idea en pausa: alinear el parpadeo por la montura de las gafas

Estado: **no está conectada** al importador. El usuario prefirió calibrar el parpadeo a mano en el Editor de poses (2026-10-24).

Qué hace `montura.py`: detecta la montura azul oscuro de las gafas, propone una caja que corta por el centro del marco (así las cejas no se
tocan y el corte no se ve) y calcula cuánto mover la imagen de parpadeo para que su montura caiga sobre la de la pose.
`test_parpadeo_montura.py` describe el comportamiento esperado (falta conectar `alinear: "montura"` en `_importar_parpadeo`).
Para retomarla: mover ambos archivos a `src/biblioteca/` y `pruebas/unitarias/` y completar la integración.
