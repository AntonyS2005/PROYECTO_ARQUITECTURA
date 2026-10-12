import os
import sys

import bcrypt

from .nucleo.configuracion import RAIZ
from .nucleo.validaciones import validar
from .repositorios.conexion import abrir_base_datos
from .repositorios.cuentas import RepositorioCuentas


def configurar():
    valores = {
        "usuario": os.getenv("USUARIO_ADMIN", "admin"),
        "clave": os.getenv("CLAVE_ADMIN"),
        "nombres": "Administración",
        "rol": "ADMINISTRADOR",
    }
    if validar("cuenta", valores):
        print(
            "Defina CLAVE_ADMIN con 8 a 64 caracteres (máximo 72 bytes).",
            file=sys.stderr,
        )
        return 1
    (RAIZ / "data").mkdir(exist_ok=True)
    conexion = abrir_base_datos(RAIZ / "data/access.sqlite")
    try:
        cuentas = RepositorioCuentas(conexion)
        if cuentas.obtener_por_usuario(valores["usuario"]):
            print("La cuenta ya existe. No se realizaron cambios.")
        else:
            hash_clave = bcrypt.hashpw(
                valores["clave"].encode("utf-8"), bcrypt.gensalt(rounds=10)
            ).decode()
            cuentas.insertar(
                valores["usuario"], hash_clave, valores["nombres"], valores["rol"]
            )
            print("Cuenta administrativa registrada.")
        return 0
    finally:
        conexion.close()


if __name__ == "__main__":
    sys.exit(configurar())
