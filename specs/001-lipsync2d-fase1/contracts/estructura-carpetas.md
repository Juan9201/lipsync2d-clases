# Contrato: estructura de carpetas

Este contrato **sustituye** la estructura inicial `personajes/<nombre>/poses/<pose>/` con
`fondo.png` dentro de la pose: con el modelo "estudio" el fondo pertenece al
**escenario**, no a la pose. Es un cambio derivado de lo acordado, no una decisión nueva.

```
<proyecto>/                         (p. ej. C:\Users\Juan 02\Desktop\Fase 1)
├── entrada/                        ← el usuario suelta aquí los archivos de assets sin ordenar
├── personajes/<personaje>/
│   └── poses/P<n>_<nombre>/
│       ├── original.png            (opcional: imagen única de partida)
│       ├── mascara.png             (generada, editable a mano)
│       ├── cuerpo.png              (RGBA, lienzo 16:9 del encuadre más abierto)
│       ├── ojos_cerrados.png       (RGBA)
│       ├── bocas/ A.png B.png C.png D.png E.png F.png G.png H.png X.png
│       └── config.yaml
├── escenarios/E<n>_<nombre>/
│   ├── fondo.png                   (opaco, 16:9)
│   └── config.yaml                 (opcional)
├── clases/                         ← guiones y audios de entrada
│   ├── <id>.txt                    (guion)
│   └── <id>.mp3                    (voz; o .wav)
├── salidas/                        ← <id>_<AAAAMMDD>.mp4  (y .part.mp4 mientras se escribe)
├── lote/
│   ├── cola.db                     (SQLite, cola persistente)
│   └── manifiestos/                (CSV de lotes)
├── cache/                          (visemas por hash de audio, fondos por plano)
├── logs/                           (un log por trabajo)
└── reglas_director.yaml            (reglas del director automático)
```

## Reglas de nombres
- Identificadores: `P<n>`, `E<n>` con `n` entero ≥ 1; sufijo `_nombre` opcional (sin
  espacios; letras, números y guion bajo, acentos permitidos).
- En `entrada/`, el **importador** clasifica por nombre:

| Archivo en `entrada/` | Destino |
|---|---|
| `P3_explicando.png` | `poses/P3_explicando/cuerpo.png` (o `original.png` si no tiene transparencia; se segmenta) |
| `P3_ojos.png` | `poses/P3_*/ojos_cerrados.png` |
| `P3_boca_A.png` … `P3_boca_X.png` | `poses/P3_*/bocas/A.png` … `X.png` |
| `E2_salon.png` / `.jpg` | `escenarios/E2_salon/fondo.png` |

- El importador valida (FR-061) y rechaza con mensaje en español cualquier archivo que no
  cumpla (nombre, PNG/RGBA, tamaño).
- Las rutas se manejan con `pathlib`; no se asume ASCII (NFR-005).
