# Contrato: sintaxis de las etiquetas del guion

Las etiquetas son texto entre corchetes dentro del guion. Son **opcionales**: sin ellas el
director automático decide todo (FR-090).

## Formas
| Forma | Efecto |
|---|---|
| `[pose:P3]` | Cambia la pose; mantiene escenario y plano activos |
| `[escenario:E2]` | Cambia el escenario |
| `[plano:PL4]` | Cambia el plano |
| `[toma:E2,P3,PL4]` | Cambia varias cosas a la vez, en cualquier orden; lo omitido se hereda (FR-055) |

- Mayúsculas/minúsculas no importan en los códigos (`pl4` = `PL4`); sí los prefijos
  reservados son en minúscula.
- Espacios dentro de los corchetes se ignoran.
- La etiqueta se refiere al punto del texto donde está escrita: la toma cambia en la
  pausa (visema X) más cercana a ese punto, con tolerancia ±2 s (FR-054).
- El texto de la etiqueta **nunca** llega al TTS (FR-012).

## Gramática (informal)
```
etiqueta  := "[" prefijo ":" valores "]"
prefijo   := "pose" | "escenario" | "plano" | "toma"
valores   := codigo { "," codigo }
codigo    := "P" N | "E" N | "PL" N        (N entero ≥ 1; PL entre 1 y 6)
```
Un `prefijo` simple admite un solo código del tipo correspondiente; `toma` admite hasta
uno de cada tipo.

## Errores (FR-056), antes de renderizar
Se informa **línea y columna del guion**, la etiqueta, el motivo y las opciones válidas:

```
Error en guion línea 14: [pose:P9] — la pose P9 no existe en el personaje "profesor".
Poses válidas: P1, P2, P3.   (Revisa el nombre de la etiqueta o sube la pose P9.)
```
Casos: código inexistente; combinación no admitida por el escenario activo;
prefijo desconocido (p. ej. `[pos:P1]` → "¿quisiste decir [pose:...]?").
Marcas entre corchetes con otros prefijos se tratan como texto para el TTS, **salvo** que
empiecen por `pos`, `escen`, `tom`, `plan` (probable errata) → advertencia.

## Prompt plantilla para que una IA etiquete un guion (se incluirá en el README)
> Te paso el guion de una clase. Insértale etiquetas de toma entre corchetes sin cambiar
> el texto. Usa [toma:E#,P#,PL#] (o [pose:P#], [plano:PL#], [escenario:E#]).
> Reglas: cambia de toma cada 20–40 s aprox.; coloca cada etiqueta al inicio de una
> frase; cambia un solo elemento (plano o pose) a la vez; no repitas la misma pose dos
> veces seguidas; usa planos cerrados (PL4–PL5) en explicaciones importantes y abiertos
> (PL2–PL3) en transiciones. Escenarios y poses disponibles: <LISTA>. Devuelve solo el guion.
