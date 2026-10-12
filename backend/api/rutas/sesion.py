import time

from fastapi import APIRouter, Request

from ...esquemas.entradas import InicioSesion
from ..dependencias import Cuenta, Cuentas, datos_sesion, guardar_sesion

rutas = APIRouter(prefix="/api")


@rutas.post("/login")
async def ingresar(datos: InicioSesion, solicitud: Request, cuentas: Cuentas):
    sesiones = solicitud.app.state.sesiones
    direccion = solicitud.client.host
    if direccion in ("127.0.0.1", "::1"):
        direccion = (
            solicitud.headers.get("x-forwarded-for", "").split(",")[-1].strip()
            or direccion
        )
    sesiones.limitar_intentos(direccion)
    cuenta = await cuentas.autenticar(datos.usuario, datos.clave)
    sesiones.intentos.pop(direccion, None)
    inicio = int(time.time())
    guardar_sesion(
        solicitud,
        sesiones.crear_token(
            cuenta,
            inicio,
            inicio + int(solicitud.app.state.configuracion.horas_sesion * 3600),
        ),
    )
    return datos_sesion(solicitud, cuenta)


@rutas.get("/me")
async def consultar_sesion(solicitud: Request, cuenta: Cuenta):
    return datos_sesion(solicitud, cuenta)


@rutas.post("/logout")
async def cerrar_sesion(solicitud: Request, cuenta: Cuenta, cuentas: Cuentas):
    cuentas.cerrar_sesion(cuenta["id"])
    solicitud.state.borrar_sesion = True
    return {"mensaje": "Sesión finalizada."}
