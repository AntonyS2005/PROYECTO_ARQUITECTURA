import ipaddress

import jwt


class ErrorAutorizacion(Exception):
    def __init__(self, mensaje, estado):
        super().__init__(mensaje)
        self.estado = estado


def validar_autorizacion(direccion, encabezado, alcance, id_nodo, clave_interna):
    direccion = ipaddress.ip_address(direccion)
    if not direccion.is_loopback and str(direccion) != "192.168.50.10":
        raise ErrorAutorizacion("Red no permitida.", 403)
    try:
        if not encabezado.startswith("Bearer ") or len(encabezado) > 4096:
            raise ValueError("Token ausente.")
        datos = jwt.decode(
            encabezado[7:],
            clave_interna,
            algorithms=["HS256"],
            audience=id_nodo,
            issuer="edge-master",
            options={"require": ["exp", "iat", "aud", "iss", "scope"]},
        )
        if (
            datos["scope"] != alcance
            or type(datos["iat"]) is not int
            or type(datos["exp"]) is not int
            or not 0 < datos["exp"] - datos["iat"] <= 60
        ):
            raise ValueError("Operación no autorizada.")
    except (jwt.PyJWTError, ValueError):
        raise ErrorAutorizacion("Solicitud no autorizada.", 401) from None
