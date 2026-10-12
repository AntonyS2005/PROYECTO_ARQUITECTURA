from fastapi import APIRouter

from ...esquemas.entradas import CambioEstado, CarneNuevo, Fotografia
from ..dependencias import Administrador, AdministradorInferencia, Carnes, validar_uuid

rutas = APIRouter(prefix="/api/carnes")


@rutas.post("", status_code=201)
async def registrar(datos: CarneNuevo, cuenta: AdministradorInferencia, carnes: Carnes):
    identificador = await carnes.registrar(datos, cuenta["id"])
    return {"mensaje": "Carné registrado.", "uuid": identificador}


@rutas.get("")
async def listar(cuenta: Administrador, carnes: Carnes):
    return carnes.listar()


@rutas.get("/{uuid}")
async def consultar(uuid: str, cuenta: Administrador, carnes: Carnes):
    return carnes.consultar(validar_uuid(uuid))


@rutas.patch("/{uuid}/foto")
async def actualizar_foto(
    uuid: str, datos: Fotografia, cuenta: AdministradorInferencia, carnes: Carnes
):
    identificador = validar_uuid(uuid)
    await carnes.actualizar_foto(identificador, datos.foto)
    return {"mensaje": "Fotografía actualizada.", "uuid": identificador}


@rutas.patch("/{uuid}")
async def cambiar_estado(
    uuid: str, datos: CambioEstado, cuenta: Administrador, carnes: Carnes
):
    carnes.cambiar_estado(validar_uuid(uuid), datos.activo)
    return {"mensaje": "Carné activado." if datos.activo else "Carné desactivado."}
