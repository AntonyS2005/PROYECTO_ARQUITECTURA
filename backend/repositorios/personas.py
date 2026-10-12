import json


class RepositorioPersonas:
    def __init__(self, conexion):
        self.conexion = conexion

    def obtener_por_uuid(self, identificador):
        return self.conexion.execute(
            "SELECT * FROM personas WHERE uuid=?", (identificador,)
        ).fetchone()

    def listar(self):
        return self.conexion.execute(
            "SELECT uuid,nombres,apellidos,activo,fecha_creacion FROM personas ORDER BY id DESC"
        ).fetchall()

    def insertar(
        self, identificador, nombres, apellidos, foto, referencia, fecha, creador
    ):
        self.conexion.execute(
            """INSERT INTO personas(uuid,nombres,apellidos,foto,vector_facial,modelo,fecha_creacion,creado_por)
            VALUES(?,?,?,?,?,?,?,?)""",
            (
                identificador,
                nombres,
                apellidos,
                foto,
                json.dumps(referencia["vectorFacial"]),
                referencia["modelo"],
                fecha,
                creador,
            ),
        )

    def actualizar_foto(self, identificador, foto, referencia):
        self.conexion.execute(
            "UPDATE personas SET foto=?,vector_facial=?,modelo=? WHERE uuid=?",
            (
                foto,
                json.dumps(referencia["vectorFacial"]),
                referencia["modelo"],
                identificador,
            ),
        )

    def cambiar_estado(self, identificador, activo):
        return (
            self.conexion.execute(
                "UPDATE personas SET activo=? WHERE uuid=?",
                (int(activo), identificador),
            ).rowcount
            > 0
        )
