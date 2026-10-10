import {
  validarConsulta,
  esAudioValido,
  identificarIntencion,
} from "../../../public/asistente/reglas.js";

export function montarAsistente(
  aplicacion,
  { autenticar, accesos, transcribir = null },
) {
  aplicacion.post(
    "/api/asistente/consulta",
    autenticar,
    (solicitud, respuesta) => {
      const errores = validarConsulta(solicitud.body?.texto);
      if (Object.keys(errores).length)
        return respuesta
          .status(422)
          .json({ mensaje: "Revise la consulta.", errores });
      const intencion = identificarIntencion(solicitud.body.texto);
      if (!intencion)
        return respuesta.status(422).json({
          mensaje: "Comando no reconocido.",
          errores: { texto: "Consulte los comandos disponibles." },
        });
      if (
        intencion.soloAdministrador &&
        solicitud.cuenta.rol !== "ADMINISTRADOR"
      )
        return respuesta.status(403).json({ mensaje: "Acceso no autorizado." });
      if (intencion.tipo === "ayuda")
        return respuesta.json({
          mensaje:
            "Comandos: abrir registro, capturar foto. Administración: abrir carnés, abrir reportes, estado de los nodos, cuántas personas hay dentro, mostrar las entradas de hoy.",
        });
      if (intencion.tipo === "navegar")
        return respuesta.json({
          mensaje: "Vista seleccionada.",
          accion: { tipo: "navegar", vista: intencion.vista },
        });
      if (intencion.tipo === "capturar")
        return respuesta.json({
          mensaje:
            "Seleccione Registro de acceso y active la cámara antes de capturar.",
          accion: { tipo: "capturar" },
        });
      const inicio = new Date();
      inicio.setHours(0, 0, 0, 0);
      const fin = new Date(inicio);
      fin.setDate(fin.getDate() + 1);
      const metricas = accesos.consultarMetricas({
        inicio: inicio.toISOString(),
        fin: fin.toISOString(),
      });
      respuesta.json({
        mensaje:
          intencion.tipo === "aforo"
            ? `Personas dentro según los registros: ${metricas.aforo}.`
            : `Entradas registradas hoy: ${metricas.entradas}.`,
      });
    },
  );
  if (transcribir) {
    let ocupado = false;
    aplicacion.post(
      "/api/asistente/transcribir",
      autenticar,
      async (solicitud, respuesta) => {
        if (!esAudioValido(solicitud.body?.audio))
          return respuesta
            .status(422)
            .json({ mensaje: "Audio no válido. Grabe hasta 8 segundos." });
        if (ocupado)
          return respuesta
            .status(503)
            .json({ mensaje: "Reconocimiento ocupado. Intente nuevamente." });
        ocupado = true;
        try {
          const texto = await transcribir(solicitud.body.audio);
          if (Object.keys(validarConsulta(texto)).length)
            return respuesta.status(422).json({
              mensaje: "No se reconoció una consulta. Intente nuevamente.",
            });
          respuesta.json({ texto });
        } catch {
          respuesta
            .status(503)
            .json({ mensaje: "Voz no disponible. Escriba la consulta." });
        } finally {
          ocupado = false;
        }
      },
    );
  }
}
