import base64
import binascii

MAXIMO_FOTOGRAFIAS = 500
MAXIMO_BYTES_FOTO = 16384


def decodificar_foto_rechazo(valor):
    if valor is None:
        return None
    try:
        if (
            not isinstance(valor, str)
            or len(valor) > ((MAXIMO_BYTES_FOTO + 2) // 3) * 4
        ):
            raise ValueError()
        foto = base64.b64decode(valor, validate=True)
        if (
            not 20 <= len(foto) <= MAXIMO_BYTES_FOTO
            or foto[:4] != b"RIFF"
            or foto[8:12] != b"WEBP"
        ):
            raise ValueError()
        if int.from_bytes(foto[4:8], "little") != len(foto) - 8:
            raise ValueError()
        return foto
    except (ValueError, binascii.Error):
        raise ValueError("Captura de rechazo no válida.") from None
