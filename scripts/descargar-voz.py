import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def descargar():
    directorio = Path(__file__).resolve().parent.parent / "backend/modulos/asistente"
    manifiesto = json.loads((directorio / "modelo.json").read_text(encoding="utf-8"))
    destino = directorio / "modelos" / (manifiesto["nombre"] + ".zip")

    def es_valido(contenido):
        return (
            len(contenido) == manifiesto["bytes"]
            and hashlib.sha256(contenido).hexdigest() == manifiesto["sha256"]
        )

    if destino.exists() and es_valido(destino.read_bytes()):
        print("Modelo de voz: SHA-256 comprobado.")
        return
    with urlopen(manifiesto["url"], timeout=120) as respuesta:
        contenido = respuesta.read(manifiesto["bytes"] + 1)
    if not es_valido(contenido):
        raise ValueError("El modelo de voz no pasó la comprobación SHA-256.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".zip.partial")
    try:
        temporal.write_bytes(contenido)
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    print("Modelo de voz descargado y verificado.")


if __name__ == "__main__":
    descargar()
