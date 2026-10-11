import asyncio
import sqlite3

import bcrypt
from fastapi import APIRouter

from ..dependencias import Administrador, BaseDatos, datos_publicos, validar_id
from ..errores import ErrorAplicacion
from ..validaciones import CambioEstado, CuentaNueva

rutas = APIRouter(prefix="/api/cuentas")


@rutas.get("")
async def listar(cuenta: Administrador, base_datos: BaseDatos):
    return [
        datos_publicos(fila)
        for fila in base_datos.execute(
            "SELECT id,usuario,nombres,rol,activo FROM usuarios ORDER BY id"
        ).fetchall()
    ]


@rutas.post("", status_code=201)
async def registrar(datos: CuentaNueva, cuenta: Administrador, base_datos: BaseDatos):
    hash_clave = await asyncio.to_thread(
        bcrypt.hashpw, datos.clave.encode("utf-8"), bcrypt.gensalt(rounds=10)
    )
    try:
        base_datos.execute(
            "INSERT INTO usuarios(usuario,hash_clave,nombres,rol) VALUES(?,?,?,?)",
            (datos.usuario, hash_clave.decode(), datos.nombres.strip(), datos.rol),
        )
    except sqlite3.IntegrityError as error:
        if "UNIQUE" in str(error):
            raise ErrorAplicacion(
                "El usuario ya está registrado.",
                409,
                {"usuario": "El usuario ya está registrado."},
            ) from None
        raise
    return {"mensaje": "Cuenta registrada."}


@rutas.patch("/{id}")
async def cambiar_estado(
    id: str, datos: CambioEstado, cuenta: Administrador, base_datos: BaseDatos
):
    identificador = validar_id(id)
    if identificador == cuenta["id"]:
        raise ErrorAplicacion("No se puede desactivar la cuenta en uso.", 409)
    resultado = base_datos.execute(
        "UPDATE usuarios SET activo=?,version=version+1 WHERE id=?",
        (int(datos.activo), identificador),
    )
    if not resultado.rowcount:
        raise ErrorAplicacion("Cuenta no encontrada.", 404)
    return {"mensaje": "Cuenta activada." if datos.activo else "Cuenta desactivada."}
