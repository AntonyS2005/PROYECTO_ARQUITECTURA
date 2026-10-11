import math
from datetime import datetime, timezone

from .errores import ErrorAplicacion
from .fotografias_rechazos import MAXIMO_FOTOGRAFIAS, decodificar_foto_rechazo

EXISTENCIA_FOTO = (
    "EXISTS(SELECT 1 FROM fotografias_rechazos f WHERE f.evento_id=e.id) AS tiene_foto"
)


def fecha_iso(fecha=None):
    return (
        (fecha or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class ServicioAccesos:
    def __init__(self, base_datos):
        self.base_datos = base_datos

    def registrar_acceso(self, persona, verificacion, usuario_id):
        base = self.base_datos
        fecha = fecha_iso()
        base.execute("BEGIN IMMEDIATE")
        try:
            actual = base.execute(
                "SELECT activo FROM personas WHERE id=?", (persona["id"],)
            ).fetchone()
            if not actual or not actual["activo"]:
                raise ErrorAplicacion("Carné no disponible.", 409)
            anterior = base.execute(
                "SELECT tipo,fecha_hora FROM eventos WHERE persona_id=? AND estado='AUTORIZADO' ORDER BY id DESC LIMIT 1",
                (persona["id"],),
            ).fetchone()
            autorizado = verificacion["similitud"] >= verificacion["umbral"]
            tipo = (
                ("SALIDA" if anterior and anterior["tipo"] == "ENTRADA" else "ENTRADA")
                if autorizado
                else None
            )
            foto = (
                None
                if autorizado
                else decodificar_foto_rechazo(verificacion.get("fotoRechazo"))
            )
            duracion = None
            if tipo == "SALIDA":
                duracion = max(
                    0,
                    (
                        datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                        - datetime.fromisoformat(
                            anterior["fecha_hora"].replace("Z", "+00:00")
                        )
                    ).total_seconds(),
                )
            registro = base.execute(
                """INSERT INTO eventos(persona_id,usuario_id,uuid,nombres,apellidos,tipo,estado,similitud,umbral,nodo,modelo,fecha_hora,duracion_segundos)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    persona["id"],
                    usuario_id,
                    persona["uuid"],
                    persona["nombres"],
                    persona["apellidos"],
                    tipo,
                    "AUTORIZADO" if autorizado else "RECHAZADO",
                    verificacion["similitud"],
                    verificacion["umbral"],
                    verificacion["nodo"],
                    verificacion["modelo"],
                    fecha,
                    duracion,
                ),
            )
            if foto:
                base.execute(
                    "INSERT INTO fotografias_rechazos(evento_id,foto) VALUES(?,?)",
                    (registro.lastrowid, foto),
                )
                base.execute(
                    "DELETE FROM fotografias_rechazos WHERE evento_id NOT IN (SELECT evento_id FROM fotografias_rechazos ORDER BY evento_id DESC LIMIT ?)",
                    (MAXIMO_FOTOGRAFIAS,),
                )
            base.execute("COMMIT")
            return base.execute(
                f"SELECT e.*,{EXISTENCIA_FOTO} FROM eventos e WHERE id=?",
                (registro.lastrowid,),
            ).fetchone()
        except Exception:
            base.execute("ROLLBACK")
            raise

    def consultar_historial(self, cuenta, periodo=None):
        if cuenta["rol"] == "OPERADOR":
            inicio = fecha_iso(
                datetime.fromtimestamp(cuenta["inicioSesion"], timezone.utc)
            )
            return self.base_datos.execute(
                f"""SELECT e.*,u.usuario,{EXISTENCIA_FOTO} FROM eventos e JOIN usuarios u ON u.id=e.usuario_id
                WHERE e.usuario_id=? AND e.fecha_hora>=? ORDER BY e.id DESC LIMIT 5""",
                (cuenta["id"], inicio),
            ).fetchall()
        return self.base_datos.execute(
            f"""SELECT e.*,u.usuario,{EXISTENCIA_FOTO} FROM eventos e JOIN usuarios u ON u.id=e.usuario_id
            WHERE e.fecha_hora>=? AND e.fecha_hora<? ORDER BY e.id DESC""",
            (periodo["inicio"], periodo["fin"]),
        ).fetchall()

    def consultar_metricas(self, periodo):
        parametros = (periodo["inicio"], periodo["fin"])
        conteos = self.base_datos.execute(
            """SELECT COALESCE(SUM(tipo='ENTRADA'),0) entradas, COALESCE(SUM(tipo='SALIDA'),0) salidas,
            COALESCE(SUM(estado='RECHAZADO'),0) rechazados, COALESCE(AVG(duracion_segundos)/60,0) promedioMinutos
            FROM eventos WHERE fecha_hora>=? AND fecha_hora<?""",
            parametros,
        ).fetchone()
        horas = self.base_datos.execute(
            """SELECT CAST(strftime('%H',fecha_hora,'localtime') AS INTEGER) hora,COUNT(*) total
            FROM eventos WHERE fecha_hora>=? AND fecha_hora<? AND estado='AUTORIZADO' GROUP BY hora""",
            parametros,
        ).fetchall()
        recurrencia = self.base_datos.execute(
            """WITH frecuencia AS (SELECT uuid,COUNT(*) total,MAX(id) ultimo FROM eventos
            WHERE fecha_hora>=? AND fecha_hora<? AND estado='AUTORIZADO' GROUP BY uuid)
            SELECT f.uuid,e.nombres || ' ' || e.apellidos nombre,f.total FROM frecuencia f
            JOIN eventos e ON e.id=f.ultimo ORDER BY f.total DESC,f.uuid LIMIT 10""",
            parametros,
        ).fetchall()
        aforo = self.base_datos.execute(
            """SELECT COUNT(*) total FROM eventos e WHERE e.estado='AUTORIZADO' AND e.tipo='ENTRADA'
            AND e.id=(SELECT MAX(x.id) FROM eventos x WHERE x.persona_id=e.persona_id AND x.estado='AUTORIZADO')""",
        ).fetchone()["total"]
        conteos["promedioMinutos"] = math.floor(conteos["promedioMinutos"] + 0.5)
        totales = {fila["hora"]: fila["total"] for fila in horas}
        return {
            **conteos,
            "aforo": aforo,
            "recurrencia": recurrencia,
            "horas": [
                {"hora": hora, "total": totales.get(hora, 0)} for hora in range(24)
            ],
        }
