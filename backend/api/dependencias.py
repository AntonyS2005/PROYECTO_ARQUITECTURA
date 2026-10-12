import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import Depends, Request

from ..nucleo.errores import ErrorAplicacion
from ..nucleo.fechas import fecha_iso
from ..nucleo.validaciones import PATRON_UUID, validar
from ..repositorios.conexion import conectar
from ..repositorios.cuentas import RepositorioCuentas
from ..repositorios.eventos import RepositorioEventos
from ..repositorios.personas import RepositorioPersonas
from ..servicios.accesos import ServicioAccesos
from ..servicios.carnes import ServicioCarnes
from ..servicios.cuentas import ServicioCuentas


async def obtener_base_datos(solicitud: Request):
    conexion = conectar(solicitud.app.state.configuracion.ruta_base)
    try:
        yield conexion
    finally:
        conexion.close()


BaseDatos = Annotated[sqlite3.Connection, Depends(obtener_base_datos)]


async def autenticar(solicitud: Request, base_datos: BaseDatos):
    try:
        cuenta, sesion = solicitud.app.state.sesiones.autenticar(
            solicitud.cookies.get("session", ""),
            RepositorioCuentas(base_datos),
            getattr(solicitud.state, "datos_token", None),
        )
    except ErrorAplicacion:
        solicitud.state.borrar_sesion = True
        raise
    guardar_sesion(solicitud, sesion)
    return cuenta


Cuenta = Annotated[dict, Depends(autenticar)]


async def exigir_administrador(cuenta: Cuenta):
    if cuenta["rol"] != "ADMINISTRADOR":
        raise ErrorAplicacion("Acceso no autorizado.", 403)
    return cuenta


Administrador = Annotated[dict, Depends(exigir_administrador)]


async def reservar_inferencia(solicitud: Request, cuenta: Cuenta):
    activas = solicitud.app.state.inferencias_activas
    if cuenta["id"] in activas:
        raise ErrorAplicacion("Verificación en curso. Espere un momento.", 429)
    if len(activas) >= 4:
        raise ErrorAplicacion("Verificaciones ocupadas. Intente nuevamente.", 429)
    activas.add(cuenta["id"])
    try:
        yield cuenta
    finally:
        activas.discard(cuenta["id"])


CuentaInferencia = Annotated[dict, Depends(reservar_inferencia)]


async def exigir_administrador_inferencia(cuenta: CuentaInferencia):
    return await exigir_administrador(cuenta)


AdministradorInferencia = Annotated[dict, Depends(exigir_administrador_inferencia)]


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


def guardar_sesion(solicitud, sesion):
    solicitud.state.token_sesion, solicitud.state.duracion_cookie = sesion


async def obtener_servicio_cuentas(base_datos: BaseDatos):
    return ServicioCuentas(RepositorioCuentas(base_datos))


async def obtener_servicio_carnes(solicitud: Request, base_datos: BaseDatos):
    return ServicioCarnes(RepositorioPersonas(base_datos), solicitud.app.state.nodos)


async def obtener_servicio_accesos(solicitud: Request, base_datos: BaseDatos):
    return ServicioAccesos(
        RepositorioEventos(base_datos),
        RepositorioPersonas(base_datos),
        solicitud.app.state.nodos,
        solicitud.app.state.configuracion.umbral_facial,
    )


Cuentas = Annotated[ServicioCuentas, Depends(obtener_servicio_cuentas)]
Carnes = Annotated[ServicioCarnes, Depends(obtener_servicio_carnes)]
Accesos = Annotated[ServicioAccesos, Depends(obtener_servicio_accesos)]
