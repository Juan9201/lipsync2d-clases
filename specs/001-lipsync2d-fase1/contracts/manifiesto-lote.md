# Contrato: manifiesto de lote y reglas del director

## Convención de entrada (los guiones hoy están sueltos y sin organizar)
En `clases/` cada clase son dos archivos con el mismo nombre base (el **identificador**):
`clase_0001.txt` + `clase_0001.mp3` (o `.wav`). Un identificador: letras, números, `_`, `-`.

## Crear un lote
```
python -m src.lote crear --carpeta clases --personaje profesor --lote 2026-10-A
```
Escanea la carpeta y genera `lote/manifiestos/<lote>.csv`; luego `python -m src.lote
encolar <csv>` crea los trabajos. Un lote de 20 y una cola de lotes de 20 son lo mismo
(FR-101): los trabajos se agrupan por la columna `lote`.

## CSV (UTF-8; solo `id` es obligatoria; el resto toma valores por defecto)
| Columna | Descripción | Defecto |
|---|---|---|
| `id` | Identificador de clase | — |
| `guion` | Ruta al `.txt` | `clases/<id>.txt` si existe, si no vacío |
| `audio` | Ruta al `.mp3`/`.wav` | `clases/<id>.mp3`; si falta, se genera con TTS (FR-010) |
| `personaje` | Nombre del personaje | argumento `--personaje` |
| `escenarios` | Códigos permitidos, separados por `;` | todos |
| `poses` | Poses permitidas, separadas por `;` | todas |
| `resolucion` | `1280x720` o `1920x1080` | `1280x720` |
| `semilla` | Semilla manual | derivada del `id` (FR-107) |
| `tts` | Proveedor si falta el audio | `gemini-studio` |

Validación al encolar: fila y problema en español (FR-101); duplicados de `id` se
rechazan; archivos inexistentes se reportan todos de una vez, no uno por uno.

## Estados de un trabajo
`pendiente → en_proceso → hecho | error`. `en_proceso` lleva latido; al reanudar, los de
latido vencido vuelven a `pendiente` y se borran sus `.part.mp4` (FR-104). Un trabajo
cuyo MP4 final ya existe y es válido se marca `hecho` sin repetirse.

## Parámetros de ejecución
`python -m src.lote correr --trabajadores 4 --espacio-minimo-gb 20` (FR-102, FR-106).
`python -m src.lote estado [--lote X]` (FR-105): terminados, en curso, errores con causa,
tiempo medio por clase y estimación de fin.

## `reglas_director.yaml` (FR-094)
```yaml
version: 1
duracion_minima_toma_s: 6        # una toma dura al menos esto
duracion_maxima_toma_s: 35       # tras esto se busca el próximo cambio
pausa_minima_para_corte_s: 0.30  # una pausa X válida para cortar dura al menos esto
no_repetir_pose_consecutiva: true
paso_de_plano_maximo: 1          # cambia el plano de a un paso (PLn → PLn±1)
alternar_escenarios: true        # cambia de escenario en cortes "largos"
cada_cuantas_tomas_cambia_escenario: 4
plano_inicial: PL2
pesos_plano: {PL2: 1.0, PL3: 1.5, PL4: 1.5, PL5: 0.8}   # preferencia relativa
```
El director sortea con la semilla de la clase (FR-093) solo entre tomas **admitidas** por
el escenario y las listas `poses`/`escenarios` de la fila (FR-092); las etiquetas manuales
(FR-091) fijan lo indicado y el director completa el resto.
