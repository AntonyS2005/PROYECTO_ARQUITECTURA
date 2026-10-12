import time

import jwt

from ..nucleo.errores import ErrorAplicacion
from ..nucleo.trafico import LimitadorSolicitudes


class Sesiones:
    def __init__(self, configuracion):
        self.configuracion = configuracion
        self.limitador = LimitadorSolicitudes()

    def crear_token(self, cuenta, inicio, vencimiento):
        ahora = int(time.time())
        token = jwt.encode(
            {
                "sub": str(cuenta["id"]),
                "version": cuenta["version"],
                "inicioSesion": inicio,
                "ultimaActividad": ahora,
                "iat": ahora,
                "exp": vencimiento,
                "iss": "control-acceso",
                "aud": "terminal-local",
            },
            self.configuracion.clave_sesion,
            algorithm="HS256",
        )
        return token, max(0, int(vencimiento - ahora))

    def leer_token(self, token):
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 4096:
                raise ValueError()
            return jwt.decode(
                token,
                self.configuracion.clave_sesion,
                algorithms=["HS256"],
                issuer="control-acceso",
                audience="terminal-local",
                options={
                    "require": [
                        "sub",
                        "exp",
                        "version",
                        "inicioSesion",
                        "ultimaActividad",
                        "iat",
                        "iss",
                        "aud",
                    ]
                },
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError):
            raise ErrorAplicacion("Sesión finalizada. Inicie sesión.", 401) from None

    def autenticar(self, token, cuentas, datos=None):
        try:
            datos = datos if datos is not None else self.leer_token(token)
            cuenta = cuentas.obtener_por_id(int(datos["sub"]))
            if (
                not cuenta
                or not cuenta["activo"]
                or datos["version"] != cuenta["version"]
                or time.time() - datos["ultimaActividad"]
                >= self.configuracion.minutos_inactividad * 60
            ):
                raise ValueError()
            cuenta["inicioSesion"] = datos["inicioSesion"]
            return cuenta, self.crear_token(cuenta, datos["inicioSesion"], datos["exp"])
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError):
            raise ErrorAplicacion("Sesión finalizada. Inicie sesión.", 401) from None

    def limitar_intentos(self, usuario):
        if self.limitador.admitir(usuario.casefold(), 8):
            raise ErrorAplicacion("Espere un minuto antes de intentar nuevamente.", 429)
