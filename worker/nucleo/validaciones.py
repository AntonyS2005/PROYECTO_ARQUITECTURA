import numpy as np


def validar_operacion(cuerpo):
    if not isinstance(cuerpo, dict) or cuerpo.get("operacion") not in (
        "registrar",
        "verificar",
        "leer-carne",
    ):
        raise ValueError("Operación no válida.")
    return cuerpo["operacion"]


def validar_referencia(cuerpo):
    umbral = cuerpo.get("umbral", 0.363)
    if (
        type(umbral) not in (int, float)
        or not np.isfinite(umbral)
        or not -1 <= umbral <= 1
    ):
        raise ValueError("Umbral no válido.")
    valores = cuerpo.get("vectorFacial")
    if (
        not isinstance(valores, list)
        or len(valores) != 128
        or any(type(valor) not in (int, float) for valor in valores)
    ):
        raise ValueError("Referencia no válida.")
    referencia = np.asarray(valores, dtype=np.float64)
    norma = np.linalg.norm(referencia)
    if not np.all(np.isfinite(referencia)) or not 0.99 < norma < 1.01:
        raise ValueError("Referencia no válida.")
    return referencia / norma, umbral
