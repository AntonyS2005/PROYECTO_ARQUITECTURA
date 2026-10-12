from contextlib import contextmanager

EXISTENCIA_FOTO = (
    "EXISTS(SELECT 1 FROM fotografias_rechazos f WHERE f.evento_id=e.id) AS tiene_foto"
)


class RepositorioEventos:
    def __init__(self, conexion):
        self.conexion = conexion

    @contextmanager
    def transaccion(self):
        self.conexion.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conexion.execute("COMMIT")
        except Exception:
            self.conexion.execute("ROLLBACK")
            raise

    def persona_activa(self, identificador):
        persona = self.conexion.execute(
            "SELECT activo FROM personas WHERE id=?", (identificador,)
        ).fetchone()
        return bool(persona and persona["activo"])

    def ultimo_autorizado(self, persona_id):
        return self.conexion.execute(
            "SELECT tipo,fecha_hora FROM eventos WHERE persona_id=? AND estado='AUTORIZADO' ORDER BY id DESC LIMIT 1",
            (persona_id,),
        ).fetchone()

    def insertar(self, evento):
        registro = self.conexion.execute(
            """INSERT INTO eventos(persona_id,usuario_id,uuid,nombres,apellidos,tipo,estado,similitud,umbral,nodo,modelo,fecha_hora,duracion_segundos)
            VALUES(:persona_id,:usuario_id,:uuid,:nombres,:apellidos,:tipo,:estado,:similitud,:umbral,:nodo,:modelo,:fecha_hora,:duracion_segundos)""",
            evento,
        )
        return registro.lastrowid

    def guardar_foto(self, identificador, foto, limite):
        self.conexion.execute(
            "INSERT INTO fotografias_rechazos(evento_id,foto) VALUES(?,?)",
            (identificador, foto),
        )
        self.conexion.execute(
            "DELETE FROM fotografias_rechazos WHERE evento_id NOT IN (SELECT evento_id FROM fotografias_rechazos ORDER BY evento_id DESC LIMIT ?)",
            (limite,),
        )

    def obtener(self, identificador):
        return self.conexion.execute(
            f"SELECT e.*,{EXISTENCIA_FOTO} FROM eventos e WHERE id=?", (identificador,)
        ).fetchone()

    def obtener_foto(self, identificador):
        captura = self.conexion.execute(
            "SELECT f.foto FROM fotografias_rechazos f JOIN eventos e ON e.id=f.evento_id WHERE e.id=? AND e.estado='RECHAZADO'",
            (identificador,),
        ).fetchone()
        return captura["foto"] if captura else None

    def historial_operador(self, usuario_id, inicio):
        return self.conexion.execute(
            f"""SELECT e.*,u.usuario,{EXISTENCIA_FOTO} FROM eventos e JOIN usuarios u ON u.id=e.usuario_id
            WHERE e.usuario_id=? AND e.fecha_hora>=? ORDER BY e.id DESC LIMIT 5""",
            (usuario_id, inicio),
        ).fetchall()

    def historial_periodo(self, periodo):
        return self.conexion.execute(
            f"""SELECT e.*,u.usuario,{EXISTENCIA_FOTO} FROM eventos e JOIN usuarios u ON u.id=e.usuario_id
            WHERE e.fecha_hora>=? AND e.fecha_hora<? ORDER BY e.id DESC""",
            (periodo["inicio"], periodo["fin"]),
        ).fetchall()

    def consultar_metricas(self, periodo):
        parametros = (periodo["inicio"], periodo["fin"])
        conteos = self.conexion.execute(
            """SELECT COALESCE(SUM(tipo='ENTRADA'),0) entradas, COALESCE(SUM(tipo='SALIDA'),0) salidas,
            COALESCE(SUM(estado='RECHAZADO'),0) rechazados, COALESCE(AVG(duracion_segundos)/60,0) promedioMinutos
            FROM eventos WHERE fecha_hora>=? AND fecha_hora<?""",
            parametros,
        ).fetchone()
        horas = self.conexion.execute(
            """SELECT CAST(strftime('%H',fecha_hora,'localtime') AS INTEGER) hora,COUNT(*) total
            FROM eventos WHERE fecha_hora>=? AND fecha_hora<? AND estado='AUTORIZADO' GROUP BY hora""",
            parametros,
        ).fetchall()
        recurrencia = self.conexion.execute(
            """WITH frecuencia AS (SELECT uuid,COUNT(*) total,MAX(id) ultimo FROM eventos
            WHERE fecha_hora>=? AND fecha_hora<? AND estado='AUTORIZADO' GROUP BY uuid)
            SELECT f.uuid,e.nombres || ' ' || e.apellidos nombre,f.total FROM frecuencia f
            JOIN eventos e ON e.id=f.ultimo ORDER BY f.total DESC,f.uuid LIMIT 10""",
            parametros,
        ).fetchall()
        aforo = self.conexion.execute(
            """SELECT COUNT(*) total FROM eventos e WHERE e.estado='AUTORIZADO' AND e.tipo='ENTRADA'
            AND e.id=(SELECT MAX(x.id) FROM eventos x WHERE x.persona_id=e.persona_id AND x.estado='AUTORIZADO')""",
        ).fetchone()["total"]
        return conteos, horas, recurrencia, aforo
