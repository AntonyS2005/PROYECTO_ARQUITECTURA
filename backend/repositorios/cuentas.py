import sqlite3

from ..nucleo.errores import UsuarioDuplicado


class RepositorioCuentas:
    def __init__(self, conexion):
        self.conexion = conexion

    def obtener_por_usuario(self, usuario):
        return self.conexion.execute(
            "SELECT * FROM usuarios WHERE usuario=?", (usuario,)
        ).fetchone()

    def obtener_por_id(self, identificador):
        return self.conexion.execute(
            "SELECT * FROM usuarios WHERE id=?", (identificador,)
        ).fetchone()

    def listar(self):
        return self.conexion.execute(
            "SELECT id,usuario,nombres,rol,activo FROM usuarios ORDER BY id"
        ).fetchall()

    def insertar(self, usuario, hash_clave, nombres, rol):
        try:
            self.conexion.execute(
                "INSERT INTO usuarios(usuario,hash_clave,nombres,rol) VALUES(?,?,?,?)",
                (usuario, hash_clave, nombres, rol),
            )
        except sqlite3.IntegrityError as error:
            if str(error).startswith("UNIQUE constraint failed: usuarios.usuario"):
                raise UsuarioDuplicado() from error
            raise

    def cambiar_estado(self, identificador, activo):
        return (
            self.conexion.execute(
                "UPDATE usuarios SET activo=?,version=version+1 WHERE id=?",
                (int(activo), identificador),
            ).rowcount
            > 0
        )

    def invalidar_sesiones(self, identificador):
        self.conexion.execute(
            "UPDATE usuarios SET version=version+1 WHERE id=?", (identificador,)
        )
