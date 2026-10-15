# Contrato: `config.yaml` de pose y de escenario

## Pose (`personajes/<personaje>/poses/P<n>_<nombre>/config.yaml`)

```yaml
version: 1
id: P3                       # obligatorio; coincide con la carpeta
nombre: explicando           # informativo
lienzo: [3840, 2160]         # tamaño de cuerpo.png (16:9); debe coincidir con el escenario
espejo: false                # FR-051: si true, se usa la vista reflejada (flip horizontal)
bocas_de: null               # "P1" = reutiliza las bocas de otra pose (misma cabeza)
ojos_de: null                # "P1" = reutiliza los ojos cerrados de otra pose (con o sin gafas igual)
anclas:                      # coordenadas en píxeles del LIENZO (origen arriba-izquierda)
  boca:  {x: 1980, y: 610, ancho: 96, angulo: 0.0}   # centro de la boca y ancho en el lienzo
  ojos:  {x: 1980, y: 520, ancho: 210, angulo: 0.0}  # centro del parche de ojos cerrados
  cabeza: {x: 1980, y: 560}                          # referencia para centrar los planos
planos:                      # opcional: sustituye los valores por defecto (ver abajo)
  PL4: {alto_relativo: 0.42, centro_y_relativo: 0.33}
movimiento:                  # FR-041/FR-042: DESACTIVADO por defecto (0 = apagado); actívalo por pose
  respiracion_escala: 0.0        # p. ej. 0.005 = ±0.5 %
  cabeza_px: 0                   # p. ej. 6 = desplazamiento máx. al hablar, en el lienzo
```

**Validaciones (FR-061):** `cuerpo.png` RGBA con el tamaño de `lienzo`; 9 bocas `A–H, X`
PNG RGBA **todas del mismo tamaño**; `ojos_cerrados.png` RGBA; `anclas` dentro del
lienzo; si `bocas_de` está definido, la pose referida existe y tiene bocas válidas.

### Planos por defecto (cámara virtual, FR-053)
`alto_relativo` = alto de la ventana de recorte / alto del lienzo. La ventana mantiene
16:9, se centra horizontalmente en `anclas.cabeza.x` y verticalmente de modo que la
cabeza quede en `centro_y_relativo` de la ventana.

| Plano | Código | `alto_relativo` | Desenfoque del fondo (σ, px de salida) |
|---|---|---|---|
| Entero | PL1 | 1.00 | 0 |
| Americano | PL2 | 0.75 | 1 |
| Cintura | PL3 | 0.58 | 2 |
| Busto | PL4 | 0.42 | 4 |
| Primer plano | PL5 | 0.30 | 6 |
| Primerísimo primer plano | PL6 | 0.18 | 9 |

Aviso FR-053: si `alto_relativo × alto_lienzo` < alto de salida (720 px a 1280×720), se
amplía y se emite el aviso "resolución insuficiente para PLn en Pn" (no bloquea).
Los valores son iniciales y se afinan en el spike S3 con assets reales.

## Escenario (`escenarios/E<n>_<nombre>/config.yaml`, opcional)

```yaml
version: 1
id: E2
nombre: salon
planos_permitidos: [PL2, PL3, PL4]   # omitido = todos
poses_permitidas: [P1, P2, P3]       # omitido = todas
peso: 1.0                            # preferencia relativa para el director (opcional)
```

Sin archivo `config.yaml` el escenario admite todos los planos y poses (FR-052).
