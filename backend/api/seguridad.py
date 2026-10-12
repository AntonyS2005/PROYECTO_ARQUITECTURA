import asyncio
import base64
import ipaddress
import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..nucleo.errores import ErrorAplicacion
from ..nucleo.trafico import LimitadorSolicitudes


class SeguridadHTTP:
    def __init__(self, app, configuracion):
        self.app = app
        self.configuracion = configuracion
        self.limitador = LimitadorSolicitudes()
        self.operaciones_activas = 0

    async def leer_cuerpo(self, receive):
        cuerpo = bytearray()
        while True:
            mensaje = await receive()
            if mensaje["type"] == "http.disconnect":
                return None
            cuerpo.extend(mensaje.get("body", b""))
            if len(cuerpo) > 450 * 1024:
                raise ErrorAplicacion("La solicitud supera el tamaño permitido.", 413)
            if not mensaje.get("more_body"):
                return bytes(cuerpo)

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
        try:
            direccion = ipaddress.ip_address(solicitud.client.host)
            if isinstance(direccion, ipaddress.IPv6Address) and direccion.ipv4_mapped:
                direccion = direccion.ipv4_mapped
        except (AttributeError, ValueError):
            return await JSONResponse({"mensaje": "Solicitud no válida."}, 400)(
                scope, receive, enviar
            )
        proxy_confiable = str(direccion) in self.configuracion.proxies_confiables
        if proxy_confiable and solicitud.headers.get("x-forwarded-proto") in (
            "https",
            "http",
        ):
            scope["scheme"] = solicitud.headers["x-forwarded-proto"]
        cliente = str(direccion)
        if proxy_confiable and solicitud.headers.get("cf-connecting-ip"):
            try:
                cliente = str(ipaddress.ip_address(solicitud.headers["cf-connecting-ip"]))
            except ValueError:
                return await JSONResponse({"mensaje": "Solicitud no válida."}, 400)(
                    scope, receive, enviar
                )
        estado["direccion_cliente"] = cliente
        limites = [("general", 3000)]
        token = solicitud.cookies.get("session")
        datos_token = None
        if token and solicitud.url.path.startswith("/api/"):
            try:
                datos_token = scope["app"].state.sesiones.leer_token(token)
            except ErrorAplicacion:
                pass
        if datos_token is not None:
            estado["datos_token"] = datos_token
            limites.append((("cuenta", datos_token["sub"]), 180))
        else:
            limites.append((("cliente", cliente), 600))
        if solicitud.url.path == "/api/login":
            limites += [("login", 120), (("login", cliente), 60)]
        for clave, limite in limites:
            espera = self.limitador.admitir(clave, limite)
            if espera:
                return await JSONResponse(
                    {"mensaje": "Demasiadas solicitudes. Espere un momento."},
                    429,
                    headers={"Retry-After": str(espera)},
                )(scope, receive, enviar)
        if solicitud.method not in ("GET", "HEAD"):
            origenes_permitidos = {
                f"{scope['scheme']}://{solicitud.headers.get('host', '')}"
            }
            if self.configuracion.origen_publico:
                origenes_permitidos.add(self.configuracion.origen_publico)
            origen = solicitud.headers.get("origin")
            if (origen and origen not in origenes_permitidos) or solicitud.headers.get(
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
            if self.operaciones_activas >= 16:
                return await JSONResponse(
                    {"mensaje": "Sistema ocupado. Intente nuevamente."},
                    429,
                    headers={"Retry-After": "2"},
                )(scope, receive, enviar)
            self.operaciones_activas += 1
            try:
                try:
                    cuerpo = await asyncio.wait_for(self.leer_cuerpo(receive), timeout=10)
                except asyncio.TimeoutError:
                    return await JSONResponse(
                        {"mensaje": "Tiempo de envío agotado."}, 408
                    )(scope, receive, enviar)
                except ErrorAplicacion as error:
                    return await JSONResponse(error.contenido, error.estado)(
                        scope, receive, enviar
                    )
                if cuerpo is None:
                    return
                recibido = False

                async def recibir():
                    nonlocal recibido
                    if not recibido:
                        recibido = True
                        return {
                            "type": "http.request",
                            "body": cuerpo,
                            "more_body": False,
                        }
                    return await receive()

                return await self.app(scope, recibir, enviar)
            finally:
                self.operaciones_activas -= 1
        await self.app(scope, receive, enviar)
