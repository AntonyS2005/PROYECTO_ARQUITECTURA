import base64

import cv2
import numpy as np


def decodificar_fotografia(foto):
    if (
        not isinstance(foto, str)
        or len(foto) > 400_000
        or not foto.startswith("data:image/jpeg;base64,")
    ):
        raise ValueError("Fotografía no válida.")
    contenido_original = base64.b64decode(foto[23:], validate=True)
    if not contenido_original.startswith(
        b"\xff\xd8\xff"
    ) or not contenido_original.endswith(b"\xff\xd9"):
        raise ValueError("Fotografía no válida.")
    imagen = cv2.imdecode(
        np.frombuffer(contenido_original, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if imagen is None or imagen.shape[0] < 80 or imagen.shape[1] < 80:
        raise ValueError("Fotografía demasiado pequeña o no válida.")
    return imagen


def crear_miniatura(imagen):
    alto, ancho = imagen.shape[:2]
    for maximo, calidad in ((240, 40), (200, 30), (160, 20)):
        escala = min(1, maximo / max(ancho, alto))
        miniatura = cv2.resize(
            imagen,
            (round(ancho * escala), round(alto * escala)),
            interpolation=cv2.INTER_AREA,
        )
        correcto, contenido = cv2.imencode(
            ".webp", miniatura, [cv2.IMWRITE_WEBP_QUALITY, calidad]
        )
        if correcto and contenido.nbytes <= 16_384:
            return base64.b64encode(contenido).decode("ascii")
    raise RuntimeError("No se pudo comprimir la captura.")
