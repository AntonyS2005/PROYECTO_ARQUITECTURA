export function crearTranscriptor(claveInterna) {
  if (!claveInterna || claveInterna.length < 32)
    throw new Error("Defina CLAVE_VOZ con al menos 32 caracteres.");
  return async (audio) => {
    const respuesta = await fetch("http://127.0.0.1:8001/transcribe", {
      method: "POST",
      redirect: "error",
      signal: AbortSignal.timeout(15000),
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${claveInterna}`,
      },
      body: JSON.stringify({ audio }),
    });
    if (!respuesta.ok) throw new Error("Servicio de voz no disponible.");
    const contenidoOriginal = await respuesta.text();
    if (contenidoOriginal.length > 2000)
      throw new Error("Respuesta de voz no válida.");
    return JSON.parse(contenidoOriginal).texto;
  };
}
