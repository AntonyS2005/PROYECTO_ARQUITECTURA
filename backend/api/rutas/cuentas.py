from fastapi import APIRouter

from ...esquemas.entradas import CambioEstado, CuentaNueva
from ..dependencias import Administrador, Cuentas, datos_publicos, validar_id

rutas = APIRouter(prefix="/api/cuentas")


@rutas.get("")
async def listar(cuenta: Administrador, cuentas: Cuentas):
    return [datos_publicos(fila) for fila in cuentas.listar()]


@rutas.post("", status_code=201)
async def registrar(datos: CuentaNueva, cuenta: Administrador, cuentas: Cuentas):
    await cuentas.registrar(datos)
    return {"mensaje": "Cuenta registrada."}


@rutas.patch("/{id}")
async def cambiar_estado(
    id: str, datos: CambioEstado, cuenta: Administrador, cuentas: Cuentas
):
    cuentas.cambiar_estado(validar_id(id), datos.activo, cuenta)
    return {"mensaje": "Cuenta activada." if datos.activo else "Cuenta desactivada."}
