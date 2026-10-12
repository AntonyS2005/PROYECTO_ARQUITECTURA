import time

import jwt

from ..nucleo.errores import ErrorAplicacion


class Sesiones:
    def __init__(self, configuracion):
        self.configuracion = configuracion
        self.intentos = {}

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

    def autenticar(self, token, cuentas):
        try:
            datos = jwt.decode(
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
                    ]
                },
            )
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

    def limitar_intentos(self, direccion):
        ahora = time.time()
        self.intentos = {
            clave: valor
            for clave, valor in self.intentos.items()
            if valor["hasta"] > ahora
        }
        intento = self.intentos.setdefault(direccion, {"total": 0, "hasta": ahora + 60})
        if intento["total"] >= 8:
            raise ErrorAplicacion("Espere un minuto antes de intentar nuevamente.", 429)
        intento["total"] += 1
        return direccion
