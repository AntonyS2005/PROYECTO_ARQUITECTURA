import {
  decodificarFotoRechazo,
  MAXIMO_FOTOGRAFIAS,
} from "./fotografias-rechazos.js";

const existenciaFoto =
  "EXISTS(SELECT 1 FROM fotografias_rechazos f WHERE f.evento_id=e.id) AS tiene_foto";

export class ServicioAccesos {
  constructor(baseDatos, reloj = () => new Date()) {
    this.baseDatos = baseDatos;
    this.reloj = reloj;
  }

  registrarAcceso(persona, verificacion, usuarioId) {
    const { baseDatos } = this;
    const fechaHora = this.reloj().toISOString();
    baseDatos.exec("BEGIN IMMEDIATE");
    try {
      const actual = baseDatos
        .prepare("SELECT activo FROM personas WHERE id=?")
        .get(persona.id);
      if (!actual?.activo)
        throw Object.assign(new Error("Carné no disponible."), { status: 409 });
      const anterior = baseDatos
        .prepare(
          `SELECT tipo,fecha_hora FROM eventos WHERE persona_id=? AND estado='AUTORIZADO'
        ORDER BY id DESC LIMIT 1`,
        )
        .get(persona.id);
      const autorizado = verificacion.similitud >= verificacion.umbral;
      const foto = autorizado
        ? null
        : decodificarFotoRechazo(verificacion.fotoRechazo);
      const tipo = autorizado
        ? anterior?.tipo === "ENTRADA"
          ? "SALIDA"
          : "ENTRADA"
        : null;
      const duracion =
        tipo === "SALIDA"
          ? Math.max(
              0,
              (Date.parse(fechaHora) - Date.parse(anterior.fecha_hora)) / 1000,
            )
          : null;
      const registroCreado = baseDatos
        .prepare(
          `INSERT INTO eventos(persona_id,usuario_id,uuid,nombres,apellidos,tipo,estado,similitud,umbral,nodo,modelo,fecha_hora,duracion_segundos)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        )
        .run(
          persona.id,
          usuarioId,
          persona.uuid,
          persona.nombres,
          persona.apellidos,
          tipo,
          autorizado ? "AUTORIZADO" : "RECHAZADO",
          verificacion.similitud,
          verificacion.umbral,
          verificacion.nodo,
          verificacion.modelo,
          fechaHora,
          duracion,
        );
      if (foto) {
        baseDatos
          .prepare(
            "INSERT INTO fotografias_rechazos(evento_id,foto) VALUES(?,?)",
          )
          .run(registroCreado.lastInsertRowid, foto);
        baseDatos
          .prepare(
            "DELETE FROM fotografias_rechazos WHERE evento_id NOT IN (SELECT evento_id FROM fotografias_rechazos ORDER BY evento_id DESC LIMIT ?)",
          )
          .run(MAXIMO_FOTOGRAFIAS);
      }
      baseDatos.exec("COMMIT");
      return baseDatos
        .prepare(`SELECT e.*,${existenciaFoto} FROM eventos e WHERE id=?`)
        .get(registroCreado.lastInsertRowid);
    } catch (error) {
      baseDatos.exec("ROLLBACK");
      throw error;
    }
  }

  consultarHistorial(cuenta, periodo) {
    if (cuenta.rol === "OPERADOR")
      return this.baseDatos
        .prepare(
          `SELECT e.*,u.usuario,${existenciaFoto} FROM eventos e JOIN usuarios u ON u.id=e.usuario_id
      WHERE e.usuario_id=? AND e.fecha_hora>=? ORDER BY e.id DESC LIMIT 5`,
        )
        .all(cuenta.id, new Date(cuenta.inicioSesion * 1000).toISOString());
    return this.baseDatos
      .prepare(
        `SELECT e.*,u.usuario,${existenciaFoto} FROM eventos e JOIN usuarios u ON u.id=e.usuario_id
      WHERE e.fecha_hora>=? AND e.fecha_hora<? ORDER BY e.id DESC`,
      )
      .all(periodo.inicio, periodo.fin);
  }

  consultarMetricas(periodo) {
    const { baseDatos } = this;
    const conteos = baseDatos
      .prepare(
        `SELECT
      COALESCE(SUM(tipo='ENTRADA'),0) entradas, COALESCE(SUM(tipo='SALIDA'),0) salidas,
      COALESCE(SUM(estado='RECHAZADO'),0) rechazados,
      COALESCE(AVG(duracion_segundos)/60,0) promedioMinutos
      FROM eventos WHERE fecha_hora>=? AND fecha_hora<?`,
      )
      .get(periodo.inicio, periodo.fin);
    const horasAgrupadas = baseDatos
      .prepare(
        `SELECT CAST(strftime('%H',fecha_hora,'localtime') AS INTEGER) hora,COUNT(*) total
      FROM eventos WHERE fecha_hora>=? AND fecha_hora<? AND estado='AUTORIZADO' GROUP BY hora`,
      )
      .all(periodo.inicio, periodo.fin);
    const recurrencia = baseDatos
      .prepare(
        `WITH frecuencia AS (
      SELECT uuid,COUNT(*) total,MAX(id) ultimo FROM eventos
      WHERE fecha_hora>=? AND fecha_hora<? AND estado='AUTORIZADO' GROUP BY uuid
    ) SELECT f.uuid,e.nombres || ' ' || e.apellidos nombre,f.total FROM frecuencia f
      JOIN eventos e ON e.id=f.ultimo ORDER BY f.total DESC,f.uuid LIMIT 10`,
      )
      .all(periodo.inicio, periodo.fin);
    const aforo = baseDatos
      .prepare(
        `SELECT COUNT(*) total FROM eventos e WHERE e.estado='AUTORIZADO' AND e.tipo='ENTRADA'
      AND e.id=(SELECT MAX(x.id) FROM eventos x WHERE x.persona_id=e.persona_id AND x.estado='AUTORIZADO')`,
      )
      .get().total;
    return {
      ...conteos,
      promedioMinutos: Math.round(conteos.promedioMinutos),
      aforo,
      recurrencia,
      horas: Array.from({ length: 24 }, (_, hora) => ({
        hora,
        total:
          horasAgrupadas.find((elemento) => elemento.hora === hora)?.total || 0,
      })),
    };
  }
}
