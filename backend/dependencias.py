import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import Depends, Request

from .base_datos import conectar
from .errores import ErrorAplicacion
from .servicio_accesos import fecha_iso
from .validaciones import PATRON_UUID, validar


async def obtener_base_datos(solicitud: Request):
    conexion = conectar(solicitud.app.state.configuracion.ruta_base)
    try:
        yield conexion
    finally:
        conexion.close()


BaseDatos = Annotated[sqlite3.Connection, Depends(obtener_base_datos)]


async def autenticar(solicitud: Request, base_datos: BaseDatos):
    return solicitud.app.state.sesiones.autenticar(solicitud, base_datos)


Cuenta = Annotated[dict, Depends(autenticar)]


async def exigir_administrador(cuenta: Cuenta):
    if cuenta["rol"] != "ADMINISTRADOR":
        raise ErrorAplicacion("Acceso no autorizado.", 403)
    return cuenta


Administrador = Annotated[dict, Depends(exigir_administrador)]


def obtener_periodo(solicitud):
    errores = validar("periodo", dict(solicitud.query_params))
    if errores:
        raise ErrorAplicacion("Revise las fechas indicadas.", errores=errores)
    zona = solicitud.app.state.zona_horaria
    inicio = datetime.combine(
        date.fromisoformat(solicitud.query_params["desde"]), time.min, zona
    )
    try:
        fin = datetime.combine(
            date.fromisoformat(solicitud.query_params["hasta"]) + timedelta(days=1),
            time.min,
            zona,
        )
    except OverflowError:
        raise ErrorAplicacion(
            "Revise las fechas indicadas.",
            errores={"hasta": "Seleccione una fecha válida."},
        ) from None
    return {"inicio": fecha_iso(inicio), "fin": fecha_iso(fin)}


def validar_uuid(valor):
    if not PATRON_UUID.fullmatch(valor):
        raise ErrorAplicacion("Identificador de carné no válido.")
    return valor.lower()


def validar_id(valor):
    if (
        len(valor) > 16
        or not valor.isascii()
        or not valor.isdecimal()
        or not 0 < int(valor) <= 9007199254740991
    ):
        raise ErrorAplicacion("Identificador no válido.")
    return int(valor)


def datos_publicos(cuenta):
    return {
        **{clave: cuenta[clave] for clave in ["id", "usuario", "nombres", "rol"]},
        "activo": bool(cuenta["activo"]),
    }


def datos_sesion(solicitud, cuenta):
    configuracion = solicitud.app.state.configuracion
    return {
        "cuenta": datos_publicos(cuenta),
        "minutosInactividad": configuracion.minutos_inactividad,
        "modulos": {
            "asistente": configuracion.asistente_habilitado,
            "voz": configuracion.voz_habilitada,
        },
    }
