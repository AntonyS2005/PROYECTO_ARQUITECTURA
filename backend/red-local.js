export function permitirRedLocal(solicitud, respuesta, continuar) {
  const direccion = solicitud.socket.remoteAddress?.replace(/^::ffff:/, "");
  if (
    direccion === "127.0.0.1" ||
    direccion === "::1" ||
    /^192\.168\.50\.\d{1,3}$/.test(direccion || "")
  )
    return continuar();
  respuesta
    .status(403)
    .json({ mensaje: "Acceso permitido únicamente desde la red local." });
}
