import base64
import binascii
import math
import re
import unicodedata
from datetime import date

PATRON_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", re.I
)
MAXIMO_CARACTERES_FOTO = 400000


def validar(tipo, valores):
    errores = {}

    def texto(clave, minimo, maximo, permitido=None, mensaje=None):
        valor = valores.get(clave)
        if isinstance(valor, str) and clave in ("nombres", "apellidos"):
            valor = valor.strip()
        if not isinstance(valor, str) or not valor.strip():
            errores[clave] = "Campo obligatorio."
        elif (
            not minimo
            <= len(valor.encode("utf-16-le", errors="surrogatepass")) // 2
            <= maximo
        ):
            errores[clave] = f"Debe contener entre {minimo} y {maximo} caracteres."
        elif permitido and not permitido(valor):
            errores[clave] = mensaje

    if tipo in ("login", "cuenta"):
        texto(
            "usuario",
            3,
            30,
            lambda valor: re.fullmatch(r"[a-zA-Z0-9._-]+", valor),
            "Solo letras, números, punto, guion y guion bajo.",
        )
        texto("clave", 8 if tipo == "cuenta" else 1, 64)
        if (
            isinstance(valores.get("clave"), str)
            and len(valores["clave"].encode("utf-8")) > 72
        ):
            errores["clave"] = "La contraseña supera el límite de 72 bytes."
    if tipo in ("carne", "cuenta"):
        for clave in ["nombres", *(["apellidos"] if tipo == "carne" else [])]:
            texto(
                clave,
                2,
                100,
                lambda valor: all(
                    unicodedata.category(letra)[0] in "LM" or letra in " .'-"
                    for letra in valor
                ),
                "Solo letras, espacios, punto, apóstrofo y guion.",
            )
    if tipo in ("acceso", "carne", "fotografia"):
        campos = ["foto"]
        if tipo == "acceso":
            campos.append("fotoCarne")
        for campo in campos:
            foto = valores.get(campo)
            if not foto:
                errores[campo] = (
                    "Capture el rostro y el carné antes de continuar."
                    if tipo == "acceso"
                    else "Seleccione una fotografía."
                )
            elif not isinstance(foto, str) or len(foto) > MAXIMO_CARACTERES_FOTO:
                errores[campo] = "La fotografía supera el tamaño permitido."
            else:
                try:
                    if not re.fullmatch(
                        r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}", foto
                    ):
                        raise ValueError()
                    contenido = base64.b64decode(foto[23:], validate=True)
                    if (
                        len(contenido) < 6
                        or not contenido.startswith(b"\xff\xd8\xff")
                        or not contenido.endswith(b"\xff\xd9")
                    ):
                        raise ValueError()
                except (ValueError, binascii.Error):
                    errores[campo] = "Se requiere una fotografía JPEG válida."
        if tipo == "acceso" and all(
            isinstance(valores.get(campo), str) for campo in ["foto", "fotoCarne"]
        ):
            if (
                len(valores["foto"]) + len(valores["fotoCarne"])
                > MAXIMO_CARACTERES_FOTO
            ):
                errores["foto"] = (
                    "La captura supera el tamaño permitido. Intente nuevamente."
                )
    if tipo == "cuenta" and valores.get("rol") not in ("ADMINISTRADOR", "OPERADOR"):
        errores["rol"] = "Seleccione un rol válido."
    if tipo == "periodo":
        for clave in ["desde", "hasta"]:
            try:
                valor = valores.get(clave)
                if not isinstance(valor, str) or not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}", valor
                ):
                    raise ValueError()
                date.fromisoformat(valor)
            except ValueError:
                errores[clave] = "Seleccione una fecha válida."
        if not errores and valores["desde"] > valores["hasta"]:
            errores["hasta"] = "Debe ser igual o posterior a la fecha inicial."
    return errores


def es_vector_facial_valido(valor):
    return (
        isinstance(valor, list)
        and len(valor) == 128
        and all(
            type(numero) in (int, float)
            and math.isfinite(numero)
            and abs(numero) <= 1.001
            for numero in valor
        )
        and 0.99 < math.sqrt(sum(numero**2 for numero in valor)) < 1.01
    )
