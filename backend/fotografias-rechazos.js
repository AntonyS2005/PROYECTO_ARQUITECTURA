export const MAXIMO_FOTOGRAFIAS = 500;
export const MAXIMO_BYTES_FOTO = 16384;

export function decodificarFotoRechazo(valor) {
  if (valor === undefined) return null;
  if (
    typeof valor !== "string" ||
    valor.length > Math.ceil(MAXIMO_BYTES_FOTO / 3) * 4 ||
    !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(
      valor,
    )
  )
    throw new Error("Captura de rechazo no válida.");
  const foto = Buffer.from(valor, "base64");
  if (
    foto.length < 20 ||
    foto.length > MAXIMO_BYTES_FOTO ||
    foto.toString("ascii", 0, 4) !== "RIFF" ||
    foto.toString("ascii", 8, 12) !== "WEBP" ||
    foto.readUInt32LE(4) !== foto.length - 8
  )
    throw new Error("Captura de rechazo no válida.");
  return foto;
}
