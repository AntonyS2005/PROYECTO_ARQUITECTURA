import ipaddress

import jwt


class ErrorAutorizacion(Exception):
    def __init__(self, mensaje, estado):
        super().__init__(mensaje)
        self.estado = estado


def validar_autorizacion(direccion, encabezado, alcance, id_nodo, clave_interna):
    direccion = ipaddress.ip_address(direccion)
    if not direccion.is_loopback and direccion not in ipaddress.ip_network(
        "192.168.50.0/24"
    ):
        raise ErrorAutorizacion("Red no permitida.", 403)
    try:
        if not encabezado.startswith("Bearer "):
            raise ValueError("Token ausente.")
        datos = jwt.decode(
            encabezado[7:],
            clave_interna,
            algorithms=["HS256"],
            audience=id_nodo,
            issuer="edge-master",
            options={"require": ["exp", "iat", "aud", "iss", "scope"]},
        )
        if datos["scope"] != alcance:
            raise ValueError("Operación no autorizada.")
    except (jwt.PyJWTError, ValueError):
        raise ErrorAutorizacion("Solicitud no autorizada.", 401) from None
