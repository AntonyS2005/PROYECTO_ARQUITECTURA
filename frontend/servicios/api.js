export async function api(ruta, { method = "GET", body: cuerpo } = {}) {
  let respuesta;
  try {
    respuesta = await fetch(`/api${ruta}`, {
      method,
      credentials: "same-origin",
      headers:
        cuerpo === undefined ? {} : { "Content-Type": "application/json" },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new Error("No se pudo conectar con el sistema.");
  }
  const datos = await respuesta.json();
  if (!respuesta.ok) {
    if (respuesta.status === 401 && ruta !== "/login")
      window.dispatchEvent(new Event("sesion-finalizada"));
    throw Object.assign(
      new Error(datos.mensaje || "No se pudo completar la operación."),
      {
        status: respuesta.status,
        codigo: datos.codigo,
        errores: datos.errores,
      },
    );
  }
  return datos;
}

export function fechaLocal(fecha = new Date()) {
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}-${String(fecha.getDate()).padStart(2, "0")}`;
}

export function fechaHora(valor) {
  return new Date(valor).toLocaleString("es-GT", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
