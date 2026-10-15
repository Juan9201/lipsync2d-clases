# Contrato: formato interno de la línea de tiempo

Estructura en memoria (dataclasses) y serializable a JSON (`cache/` y depuración). El eje
de tiempo es el del audio; la unidad es el **frame** (25 fps) para todo lo que el render
consume, y segundos para lo que viene de Rhubarb.

```json
{
  "version": 1,
  "fps": 25,
  "duracion_s": 301.44,
  "n_frames": 7536,
  "semilla": 3141592653,
  "visemas": [ {"f0": 0, "f1": 12, "v": "X"}, {"f0": 12, "f1": 15, "v": "D"} ],
  "tomas":   [ {"f0": 0, "escenario": "E1", "pose": "P1", "plano": "PL2"},
               {"f0": 812, "escenario": "E1", "pose": "P1", "plano": "PL4"} ],
  "parpadeos": [ {"f0": 61, "frames": 4} ],
  "hablando": [ {"f0": 12, "f1": 7490} ]
}
```

## Reglas e invariantes (se verifican con tests)
- **Visemas:** intervalos `[f0, f1)` contiguos y sin huecos que cubren `0..n_frames`;
  `v ∈ {A,B,C,D,E,F,G,H,X}`; ninguno dura < 2 frames salvo `A` (FR-022).
- **Tomas:** `f0` estrictamente creciente; la primera empieza en `f0 = 0`; todo cambio
  cae en un frame cuyo visema es `X` (o en el límite de frase si se avisó, FR-054); cada
  toma cumple las restricciones del escenario (FR-052).
- **Parpadeos:** intervalos entre inicios en [2, 6] s (50–150 frames), duración 3–5
  frames; derivados de la semilla (FR-040).
- **`hablando`:** frames con voz (visema ≠ `X`), para activar el movimiento leve
  (FR-042); se suaviza con una ventana para evitar entrar/salir a cada pausa breve.
- **Semilla:** `semilla = SHA-256(clase_id)[0:8]` (entero sin signo) combinada con la
  semilla global opcional (FR-107); determina parpadeos, director y movimiento (NFR-004).
- **Respiración y movimiento** no se guardan: son funciones puras de `(frame, semilla)`.

## Productor → consumidor
`lipsync` (Rhubarb → visemas, suavizado) → `director`/`etiquetas` (tomas) → `animation`
(parpadeos, `hablando`, funciones de movimiento) → `timeline` ensambla y valida →
`compositor` la consulta por frame (acceso O(1) con índices precalculados).
