import asyncio
import time

import bcrypt
from fastapi import APIRouter, Request

from ..dependencias import BaseDatos, Cuenta, datos_sesion
from ..errores import ErrorAplicacion
from ..validaciones import InicioSesion

rutas = APIRouter(prefix="/api")


@rutas.post("/login")
async def ingresar(datos: InicioSesion, solicitud: Request, base_datos: BaseDatos):
    sesiones = solicitud.app.state.sesiones
    direccion = sesiones.limitar_intentos(solicitud)
    cuenta = base_datos.execute(
        "SELECT * FROM usuarios WHERE usuario=?", (datos.usuario,)
    ).fetchone()
    correcto = (
        cuenta
        and cuenta["activo"]
        and await asyncio.to_thread(
            bcrypt.checkpw,
            datos.clave.encode("utf-8"),
            cuenta["hash_clave"].encode("ascii"),
        )
    )
    if not correcto:
        raise ErrorAplicacion(
            "Usuario o contraseña no válidos.",
            401,
            {
                "usuario": "Revise las credenciales.",
                "clave": "Revise las credenciales.",
            },
        )
    sesiones.intentos.pop(direccion, None)
    inicio = int(time.time())
    sesiones.establecer(
        solicitud,
        cuenta,
        inicio,
        inicio + int(solicitud.app.state.configuracion.horas_sesion * 3600),
    )
    return datos_sesion(solicitud, cuenta)


@rutas.get("/me")
async def consultar_sesion(solicitud: Request, cuenta: Cuenta):
    return datos_sesion(solicitud, cuenta)


@rutas.post("/logout")
async def cerrar_sesion(solicitud: Request, cuenta: Cuenta, base_datos: BaseDatos):
    base_datos.execute(
        "UPDATE usuarios SET version=version+1 WHERE id=?", (cuenta["id"],)
    )
    solicitud.state.borrar_sesion = True
    return {"mensaje": "Sesión finalizada."}
