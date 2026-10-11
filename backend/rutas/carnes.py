import base64
import io
import json
from uuid import uuid4

import qrcode
from fastapi import APIRouter, Request

from ..dependencias import Administrador, BaseDatos, validar_uuid
from ..errores import ErrorAplicacion
from ..gestor_nodos import es_vector_facial_valido, nodos_no_disponibles
from ..servicio_accesos import fecha_iso
from ..validaciones import CambioEstado, CarneNuevo, Fotografia

rutas = APIRouter(prefix="/api/carnes")


async def obtener_referencia(solicitud, foto):
    nodos = solicitud.app.state.nodos
    if not nodos:
        raise nodos_no_disponibles()
    resultado = await nodos.ejecutar_inferencia("registrar", {"foto": foto})
    if (
        not es_vector_facial_valido(resultado.get("vectorFacial"))
        or resultado.get("modelo") != "sface-2021dec"
    ):
        raise nodos_no_disponibles()
    return resultado


@rutas.post("", status_code=201)
async def registrar(
    datos: CarneNuevo, solicitud: Request, cuenta: Administrador, base_datos: BaseDatos
):
    resultado = await obtener_referencia(solicitud, datos.foto)
    identificador = str(uuid4())
    base_datos.execute(
        """INSERT INTO personas(uuid,nombres,apellidos,foto,vector_facial,modelo,fecha_creacion,creado_por)
        VALUES(?,?,?,?,?,?,?,?)""",
        (
            identificador,
            datos.nombres.strip(),
            datos.apellidos.strip(),
            datos.foto,
            json.dumps(resultado["vectorFacial"]),
            resultado["modelo"],
            fecha_iso(),
            cuenta["id"],
        ),
    )
    return {"mensaje": "Carné registrado.", "uuid": identificador}


@rutas.get("")
async def listar(cuenta: Administrador, base_datos: BaseDatos):
    return base_datos.execute(
        "SELECT uuid,nombres,apellidos,activo,fecha_creacion FROM personas ORDER BY id DESC"
    ).fetchall()


@rutas.get("/{uuid}")
async def consultar(uuid: str, cuenta: Administrador, base_datos: BaseDatos):
    persona = base_datos.execute(
        "SELECT uuid,nombres,apellidos,foto,activo,fecha_creacion FROM personas WHERE uuid=?",
        (validar_uuid(uuid),),
    ).fetchone()
    if not persona:
        raise ErrorAplicacion("Carné no encontrado.", 404)
    imagen = qrcode.make(persona["uuid"], border=4).resize((300, 300), resample=0)
    contenido = io.BytesIO()
    imagen.save(contenido, format="PNG")
    return {
        **persona,
        "qr": "data:image/png;base64,"
        + base64.b64encode(contenido.getvalue()).decode(),
    }


@rutas.patch("/{uuid}/foto")
async def actualizar_foto(
    uuid: str,
    datos: Fotografia,
    solicitud: Request,
    cuenta: Administrador,
    base_datos: BaseDatos,
):
    identificador = validar_uuid(uuid)
    if not base_datos.execute(
        "SELECT id FROM personas WHERE uuid=?", (identificador,)
    ).fetchone():
        raise ErrorAplicacion("Carné no encontrado.", 404)
    resultado = await obtener_referencia(solicitud, datos.foto)
    base_datos.execute(
        "UPDATE personas SET foto=?,vector_facial=?,modelo=? WHERE uuid=?",
        (
            datos.foto,
            json.dumps(resultado["vectorFacial"]),
            resultado["modelo"],
            identificador,
        ),
    )
    return {"mensaje": "Fotografía actualizada.", "uuid": identificador}


@rutas.patch("/{uuid}")
async def cambiar_estado(
    uuid: str, datos: CambioEstado, cuenta: Administrador, base_datos: BaseDatos
):
    resultado = base_datos.execute(
        "UPDATE personas SET activo=? WHERE uuid=?",
        (int(datos.activo), validar_uuid(uuid)),
    )
    if not resultado.rowcount:
        raise ErrorAplicacion("Carné no encontrado.", 404)
    return {"mensaje": "Carné activado." if datos.activo else "Carné desactivado."}
