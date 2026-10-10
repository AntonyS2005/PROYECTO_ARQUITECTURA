import { readFile, mkdir, writeFile, rename, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
const manifiesto = JSON.parse(
  await readFile(
    new URL("../modulos/asistente/modelo.json", import.meta.url),
    "utf8",
  ),
);
const directorio = new URL("../modulos/asistente/modelos/", import.meta.url);
const destino = new URL(`${manifiesto.nombre}.zip`, directorio);
const esValido = (bytes) =>
  bytes.length === manifiesto.bytes &&
  createHash("sha256").update(bytes).digest("hex") === manifiesto.sha256;
await mkdir(directorio, { recursive: true });
let existente;
try {
  existente = await readFile(destino);
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
if (existente && esValido(existente)) {
  console.log("Modelo de voz: SHA-256 comprobado.");
} else {
  const respuesta = await fetch(manifiesto.url, {
    signal: AbortSignal.timeout(120000),
  });
  if (!respuesta.ok) throw new Error("No se pudo descargar el modelo de voz.");
  const bytes = Buffer.from(await respuesta.arrayBuffer());
  if (!esValido(bytes))
    throw new Error("El modelo de voz no pasó la comprobación SHA-256.");
  const temporal = new URL(`${manifiesto.nombre}.zip.partial`, directorio);
  try {
    await writeFile(temporal, bytes);
    await rename(temporal, destino);
  } finally {
    await rm(temporal, { force: true });
  }
  console.log(
    "Modelo de voz descargado y verificado. Instalarlo con configure-assistant.sh voice.",
  );
}
