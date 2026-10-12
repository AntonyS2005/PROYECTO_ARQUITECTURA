import asyncio

import bcrypt

from ..nucleo.errores import ErrorAplicacion, UsuarioDuplicado


class ServicioCuentas:
    def __init__(self, cuentas):
        self.cuentas = cuentas

    def listar(self):
        return self.cuentas.listar()

    async def autenticar(self, usuario, clave):
        cuenta = self.cuentas.obtener_por_usuario(usuario)
        if (
            not cuenta
            or not cuenta["activo"]
            or not await asyncio.to_thread(
                bcrypt.checkpw,
                clave.encode("utf-8"),
                cuenta["hash_clave"].encode("ascii"),
            )
        ):
            raise ErrorAplicacion(
                "Usuario o contraseña no válidos.",
                401,
                {
                    "usuario": "Revise las credenciales.",
                    "clave": "Revise las credenciales.",
                },
            )
        return cuenta

    async def registrar(self, datos):
        hash_clave = await asyncio.to_thread(
            bcrypt.hashpw, datos.clave.encode("utf-8"), bcrypt.gensalt(rounds=10)
        )
        try:
            self.cuentas.insertar(
                datos.usuario, hash_clave.decode(), datos.nombres.strip(), datos.rol
            )
        except UsuarioDuplicado:
            raise ErrorAplicacion(
                "El usuario ya está registrado.",
                409,
                {"usuario": "El usuario ya está registrado."},
            ) from None

    def cambiar_estado(self, identificador, activo, cuenta_actual):
        if identificador == cuenta_actual["id"]:
            raise ErrorAplicacion("No se puede desactivar la cuenta en uso.", 409)
        if not self.cuentas.cambiar_estado(identificador, activo):
            raise ErrorAplicacion("Cuenta no encontrada.", 404)

    def cerrar_sesion(self, identificador):
        self.cuentas.invalidar_sesiones(identificador)
