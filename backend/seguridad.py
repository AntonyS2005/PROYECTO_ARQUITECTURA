import base64
import ipaddress
import secrets
import time

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .errores import ErrorAplicacion


class Sesiones:
    def __init__(self, configuracion):
        self.configuracion = configuracion
        self.intentos = {}

    def establecer(self, solicitud, cuenta, inicio, vencimiento):
        ahora = int(time.time())
        solicitud.state.token_sesion = jwt.encode(
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
        solicitud.state.duracion_cookie = max(0, int(vencimiento - ahora))

    def autenticar(self, solicitud, base_datos):
        try:
            datos = jwt.decode(
                solicitud.cookies.get("session", ""),
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
            cuenta = base_datos.execute(
                "SELECT * FROM usuarios WHERE id=?", (int(datos["sub"]),)
            ).fetchone()
            if (
                not cuenta
                or not cuenta["activo"]
                or datos["version"] != cuenta["version"]
                or time.time() - datos["ultimaActividad"]
                >= self.configuracion.minutos_inactividad * 60
            ):
                raise ValueError()
            cuenta["inicioSesion"] = datos["inicioSesion"]
            self.establecer(solicitud, cuenta, datos["inicioSesion"], datos["exp"])
            return cuenta
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError):
            solicitud.state.borrar_sesion = True
            raise ErrorAplicacion("Sesión finalizada. Inicie sesión.", 401) from None

    def limitar_intentos(self, solicitud):
        ahora = time.time()
        self.intentos = {
            clave: valor
            for clave, valor in self.intentos.items()
            if valor["hasta"] > ahora
        }
        direccion = (
            solicitud.headers.get("x-forwarded-for", "").split(",")[-1].strip()
            if solicitud.client.host in ("127.0.0.1", "::1")
            else solicitud.client.host
        )
        direccion = direccion or solicitud.client.host
        intento = self.intentos.setdefault(direccion, {"total": 0, "hasta": ahora + 60})
        if intento["total"] >= 8:
            raise ErrorAplicacion("Espere un minuto antes de intentar nuevamente.", 429)
        intento["total"] += 1
        return direccion


class SeguridadHTTP:
    def __init__(self, app, configuracion):
        self.app = app
        self.configuracion = configuracion

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        estado = scope.setdefault("state", {})
        estado["nonce"] = base64.b64encode(secrets.token_bytes(16)).decode()
        nonce = estado["nonce"]
        cabeceras = {
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "referrer-policy": "same-origin",
            "content-security-policy": f"default-src 'self'; script-src 'self'; style-src 'self' 'nonce-{nonce}'; style-src-attr 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            "permissions-policy": f"camera=(self), microphone={'(self)' if self.configuracion.voz_habilitada else '()'}",
        }

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                mensaje["headers"] += [
                    (clave.encode(), valor.encode())
                    for clave, valor in cabeceras.items()
                ]
                cookie = Response()
                opciones = {
                    "httponly": True,
                    "secure": self.configuracion.cookie_segura,
                    "samesite": "strict",
                    "path": "/",
                }
                if estado.get("borrar_sesion"):
                    cookie.delete_cookie("session", **opciones)
                elif estado.get("token_sesion"):
                    cookie.set_cookie(
                        "session",
                        estado["token_sesion"],
                        max_age=estado["duracion_cookie"],
                        **opciones,
                    )
                mensaje["headers"] += [
                    cabecera
                    for cabecera in cookie.raw_headers
                    if cabecera[0] == b"set-cookie"
                ]
            await send(mensaje)

        solicitud = Request(scope)
        direccion = ipaddress.ip_address(solicitud.client.host.replace("::ffff:", ""))
        if not direccion.is_loopback and direccion not in ipaddress.ip_network(
            "192.168.50.0/24"
        ):
            return await JSONResponse(
                {"mensaje": "Acceso permitido únicamente desde la red local."}, 403
            )(scope, receive, enviar)
        if direccion.is_loopback and solicitud.headers.get("x-forwarded-proto") in (
            "https",
            "http",
        ):
            scope["scheme"] = solicitud.headers["x-forwarded-proto"]
        if solicitud.method not in ("GET", "HEAD"):
            esperado = f"{scope['scheme']}://{solicitud.headers.get('host', '')}"
            origen = solicitud.headers.get("origin")
            if (origen and origen != esperado) or solicitud.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                return await JSONResponse({"mensaje": "Solicitud no permitida."}, 403)(
                    scope, receive, enviar
                )
            if (
                solicitud.headers.get("content-type", "").split(";")[0].strip()
                != "application/json"
            ):
                return await JSONResponse(
                    {"mensaje": "Formato de solicitud no válido."}, 415
                )(scope, receive, enviar)
            cuerpo = bytearray()
            while True:
                mensaje = await receive()
                if mensaje["type"] == "http.disconnect":
                    return
                cuerpo.extend(mensaje.get("body", b""))
                if len(cuerpo) > 450 * 1024:
                    return await JSONResponse(
                        {"mensaje": "La solicitud supera el tamaño permitido."}, 413
                    )(scope, receive, enviar)
                if not mensaje.get("more_body"):
                    break
            recibido = False

            async def recibir():
                nonlocal recibido
                if not recibido:
                    recibido = True
                    return {
                        "type": "http.request",
                        "body": bytes(cuerpo),
                        "more_body": False,
                    }
                return await receive()

            return await self.app(scope, recibir, enviar)
        await self.app(scope, receive, enviar)
