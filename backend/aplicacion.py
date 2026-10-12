import json
import logging
import os
import time
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .api.rutas import accesos, carnes, cuentas, sesion, sistema
from .api.seguridad import SeguridadHTTP
from .infraestructura.nodos import GestorNodos
from .modulos.asistente.rutas import crear_rutas
from .modulos.asistente.transcriptor import Transcriptor
from .nucleo.configuracion import RAIZ, Configuracion
from .nucleo.errores import ErrorAplicacion
from .repositorios.conexion import abrir_base_datos
from .servicios.sesiones import Sesiones


def crear_aplicacion(configuracion=None, nodos=None):
    configuracion = configuracion or Configuracion.cargar()

    @asynccontextmanager
    async def ciclo_vida(aplicacion):
        configuracion.ruta_base.parent.mkdir(parents=True, exist_ok=True)
        conexion = abrir_base_datos(configuracion.ruta_base)
        conexion.close()
        try:
            yield
        finally:
            if aplicacion.state.nodos:
                await aplicacion.state.nodos.cerrar()
            if aplicacion.state.transcriptor:
                await aplicacion.state.transcriptor.cerrar()

    aplicacion = FastAPI(
        title="Control de acceso",
        lifespan=ciclo_vida,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    aplicacion.state.configuracion = configuracion
    aplicacion.state.sesiones = Sesiones(configuracion)
    aplicacion.state.inicio = time.monotonic()
    aplicacion.state.inferencias_activas = set()
    aplicacion.state.zona_horaria = ZoneInfo(os.getenv("TZ", "America/Mexico_City"))
    if nodos is None and os.getenv("NODOS"):
        nodos = GestorNodos(
            json.loads(os.environ["NODOS"]),
            os.getenv("CLAVE_NODOS", ""),
            int(os.getenv("ESPERA_NODOS_MS", "5000")),
        )
    aplicacion.state.nodos = nodos
    aplicacion.state.transcriptor = (
        Transcriptor(configuracion.clave_voz) if configuracion.voz_habilitada else None
    )
    aplicacion.add_middleware(SeguridadHTTP, configuracion=configuracion)

    @aplicacion.exception_handler(ErrorAplicacion)
    async def error_aplicacion(solicitud: Request, error: ErrorAplicacion):
        return JSONResponse(error.contenido, status_code=error.estado)

    @aplicacion.exception_handler(RequestValidationError)
    async def error_validacion(solicitud: Request, error: RequestValidationError):
        if any(detalle["type"] == "json_invalid" for detalle in error.errors()):
            return JSONResponse({"mensaje": "Formato de solicitud no válido."}, 400)
        errores = {
            str(detalle["loc"][-1]): "Campo obligatorio."
            if detalle["type"] == "missing"
            else "Dato no válido."
            for detalle in error.errors()
        }
        return JSONResponse(
            {"mensaje": "Revise los campos indicados.", "errores": errores}, 422
        )

    @aplicacion.exception_handler(HTTPException)
    async def error_http(solicitud: Request, error: HTTPException):
        return JSONResponse(
            {
                "mensaje": "Recurso no encontrado."
                if error.status_code == 404
                else "Solicitud no válida."
            },
            error.status_code,
        )

    @aplicacion.exception_handler(Exception)
    async def error_interno(solicitud: Request, error: Exception):
        logging.exception("No se pudo completar la operación.")
        return JSONResponse({"mensaje": "No se pudo completar la operación."}, 500)

    @aplicacion.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    @aplicacion.api_route(
        "/index.html", methods=["GET", "HEAD"], response_class=HTMLResponse
    )
    async def inicio(solicitud: Request):
        pagina = (RAIZ / "public/index.html").read_text(encoding="utf-8")
        return HTMLResponse(pagina.replace("__NONCE__", solicitud.state.nonce))

    for modulo in [sesion, carnes, accesos, cuentas, sistema]:
        aplicacion.include_router(modulo.rutas)
    if configuracion.asistente_habilitado:
        aplicacion.include_router(crear_rutas(configuracion.voz_habilitada))

    @aplicacion.api_route(
        "/api/{ruta:path}",
        methods=["GET", "POST", "PATCH", "DELETE", "PUT", "HEAD", "OPTIONS"],
    )
    async def recurso_ausente(ruta: str):
        raise ErrorAplicacion("Recurso no encontrado.", 404)

    aplicacion.mount("/", StaticFiles(directory=RAIZ / "public"), name="publico")
    return aplicacion
