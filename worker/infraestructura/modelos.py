import hashlib
import json

from ..nucleo.configuracion import DIRECTORIO_RAIZ


def cargar_modelos(directorio):
    manifiesto = json.loads(
        (DIRECTORIO_RAIZ / "modelos.json").read_text(encoding="utf-8")
    )
    rutas = {}
    for modelo in manifiesto["modelos"]:
        ruta = directorio / modelo["archivo"]
        if (
            ruta.stat().st_size != modelo["bytes"]
            or hashlib.sha256(ruta.read_bytes()).hexdigest() != modelo["sha256"]
        ):
            raise RuntimeError("Modelo ausente o con integridad no válida.")
        rutas[modelo["archivo"]] = str(ruta)
    return rutas
