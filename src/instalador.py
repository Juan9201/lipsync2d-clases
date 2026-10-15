"""Descargas verificadas del instalador (FR-001, P4): cada archivo se comprueba con SHA-256.

Uso:  python -m src.instalador            (lee herramientas/manifiesto_descargas.json)
"""
import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from src.errores import EntornoIncompleto
from src.registro import obtener_logger

log = obtener_logger("instalador")
BLOQUE = 1024 * 1024


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()


def descargar_verificado(url: str, destino: Path, sha256: str) -> Path:
    """Descarga `url` a `destino` y verifica el SHA-256. Si ya existe y coincide, no descarga.
    Ante un checksum distinto borra lo descargado y lanza un error accionable."""
    destino = Path(destino)
    sha256 = sha256.lower()
    if destino.is_file() and sha256_de(destino) == sha256:
        log.info("Ya existe y coincide: %s", destino.name)
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".descarga")
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(parcial, "wb") as f:
            shutil.copyfileobj(r, f, BLOQUE)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        parcial.unlink(missing_ok=True)
        raise EntornoIncompleto(
            f"No se pudo descargar {url} ({exc})",
            "Revisa tu conexión a internet y vuelve a ejecutar instalar.ps1") from exc
    obtenido = sha256_de(parcial)
    if obtenido != sha256:
        parcial.unlink(missing_ok=True)
        raise EntornoIncompleto(
            f"El checksum de {destino.name} no coincide (esperado {sha256[:12]}…, obtenido {obtenido[:12]}…)",
            "Vuelve a intentarlo; si persiste, el archivo cambió en el origen y hay que actualizar "
            "herramientas/manifiesto_descargas.json")
    parcial.replace(destino)
    log.info("Descargado y verificado: %s", destino.name)
    return destino


def extraer_zip(zip_ruta: Path, destino: Path, quitar_raiz: bool = False) -> None:
    """Extrae un zip rechazando rutas que salgan de `destino` (zip slip).
    Con `quitar_raiz`, la carpeta superior común del zip no se crea en `destino`."""
    destino = Path(destino).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_ruta) as z:
        miembros = [m for m in z.namelist() if not m.endswith("/")]
        raiz = ""
        if quitar_raiz:
            primeros = {m.split("/", 1)[0] for m in miembros}
            if len(primeros) == 1:
                raiz = primeros.pop() + "/"
        for miembro in miembros:
            relativo = miembro[len(raiz):] if raiz and miembro.startswith(raiz) else miembro
            objetivo = (destino / relativo).resolve()
            if destino != objetivo and destino not in objetivo.parents:
                raise EntornoIncompleto(
                    f"El archivo {Path(zip_ruta).name} contiene una ruta no permitida ({miembro})",
                    "No uses este paquete; vuelve a descargarlo desde el origen oficial")
            objetivo.parent.mkdir(parents=True, exist_ok=True)
            with z.open(miembro) as origen, open(objetivo, "wb") as f:
                shutil.copyfileobj(origen, f, BLOQUE)


def instalar_desde_manifiesto(raiz: Path, preparacion: bool = False) -> None:
    """Descarga y extrae lo listado en herramientas/manifiesto_descargas.json. Los items con
    grupo «preparacion» (modelos pesados de segmentación e inpainting) solo con `preparacion`."""
    ruta = Path(raiz) / "herramientas" / "manifiesto_descargas.json"
    if not ruta.is_file():
        raise EntornoIncompleto(
            f"No existe {ruta.name}", "Pide que se complete el manifiesto de descargas")
    for item in json.loads(ruta.read_text(encoding="utf-8")):
        if item.get("grupo") == "preparacion" and not preparacion:
            continue
        archivo = Path(raiz) / "herramientas" / "descargas" / item["archivo"]
        descargar_verificado(item["url"], archivo, item["sha256"])
        if item.get("extraer_en"):
            extraer_zip(archivo, Path(raiz) / item["extraer_en"], item.get("quitar_raiz", False))
        if item.get("copiar_a"):
            destino = Path(raiz) / item["copiar_a"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archivo, destino)


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="python -m src.instalador")
    p.add_argument("--preparacion", action="store_true", help="Incluye los modelos de segmentación e inpainting")
    args = p.parse_args(argv)
    raiz = Path(__file__).resolve().parent.parent
    try:
        instalar_desde_manifiesto(raiz, args.preparacion)
    except EntornoIncompleto as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
