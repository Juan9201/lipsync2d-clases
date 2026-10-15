# Guía rápida (quickstart.md)

> **Borrador de objetivo.** Describe cómo se usará el sistema cuando esté construido; los
> comandos todavía no existen y se validan en la Fase 6 (SC-003). Rutas con espacios van
> entre comillas.

## 1. Instalar (una vez)
```powershell
cd "C:\Users\Juan 02\Desktop\Fase 1"
.\instalar.ps1            # crea .venv, instala dependencias, descarga ffmpeg, Rhubarb y modelos
.\verificar.ps1           # informa el estado de cada dependencia y cómo corregirla (FR-002)
```
Para preparar poses desde una imagen única, instala también el grupo opcional:
`.\instalar.ps1 -Preparacion`

## 2. Preparar assets (una vez por pose y escenario)
1. Genera los assets con tu IA siguiendo `contracts/guia-assets.md` (se copiará como
   `assets/README.md`).
2. Suelta todos los archivos, con sus nombres (`P1_profesor.png`, `P1_boca_A.png`,
   `E1_salon.png`…), en la carpeta `entrada/`.
3. Impórtalos (valida y ordena en las carpetas correctas):
```powershell
python -m src.biblioteca importar
```
   También puedes arrastrarlos en la pestaña **Biblioteca** de la interfaz (`python -m src.ui`).
4. Si falta la separación de personaje: `python -m src.prep pose P1` (genera `mascara.png`,
   que puedes retocar y reimportar con `--mascara`).
5. Calibra boca y ojos con clics en la pestaña **Calibración**, o edita `config.yaml`.

## 3. Probar rápido
```powershell
python -m src.render --previa --guion clases\clase_0001.txt --personaje profesor --audio clases\clase_0001.mp3
```
Genera 5 segundos en `salidas\` (FR-063). Con bocas placeholder funciona sin assets propios.

## 4. Renderizar una clase
```powershell
python -m src.render --guion clases\clase_0001.txt --personaje profesor --audio clases\clase_0001.mp3 --seed 7
```
Sin `--audio`, genera la voz con `--tts gemini-studio` (por defecto) o `edge`; el género de la voz sale de `tts.yaml` (`genero: hombre|mujer`) o de `--genero`.
Resultado: `salidas\clase_0001_AAAAMMDD.mp4`.

## 5. Producir muchas clases (lotes)
Deja cada clase en `clases\` como un par con el mismo nombre: `clase_0001.txt` (guion) y
`clase_0001.mp3` (voz). Si solo tienes el guion, el audio se genera con tu webapp de Gemini.
```powershell
python -m src.tts lote --carpeta clases --genero hombre            # genera los .mp3 que falten (reanudable)
python -m src.lote crear --carpeta clases --personaje profesor --lote prueba-1
python -m src.lote encolar lote\manifiestos\prueba-1.csv
python -m src.lote correr --trabajadores 4 --espacio-minimo-gb 20  # procesa la cola en paralelo
python -m src.lote estado                                          # progreso, ritmo, estimación y errores
python -m src.lote reintentar                                      # las clases con error vuelven a la cola
```
Si se apaga la PC o cierras la ventana, vuelve a ejecutar `correr`: retoma lo que quedó a medias y
no repite lo terminado. Si el disco baja de 20 GB libres, los trabajadores esperan y siguen solos
cuando liberes espacio.

**Prueba escalonada recomendada:** primero 1 clase, luego 4 y, si todo se ve bien, 20. Cada lote lleva
su propia etiqueta (`--lote prueba-1`, `prueba-4`, `prueba-20`); `estado --lote prueba-4` muestra solo ese.

## 6. Si algo falla
Los errores salen en español con la acción a seguir. Los registros por trabajo están en
`logs\`. `.\verificar.ps1` revisa el entorno.
