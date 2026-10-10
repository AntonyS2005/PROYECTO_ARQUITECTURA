import { readFile, mkdir, writeFile, rename, rm } from "node:fs/promises";
import { createHash } from "node:crypto";

const manifiesto = JSON.parse(
  await readFile(new URL("../worker/modelos.json", import.meta.url), "utf8"),
);
const destino = new URL("../worker/modelos/", import.meta.url);
await mkdir(destino, { recursive: true });
for (const modelo of manifiesto.modelos) {
  const archivo = new URL(modelo.archivo, destino);
  try {
    const existente = await readFile(archivo);
    if (
      createHash("sha256").update(existente).digest("hex") === modelo.sha256
    ) {
      console.log(`${modelo.archivo}: integridad comprobada.`);
      continue;
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const respuesta = await fetch(
    `https://media.githubusercontent.com/media/${manifiesto.repositorio}/${manifiesto.commit}/models/${modelo.carpeta}/${modelo.archivo}`,
    { signal: AbortSignal.timeout(120000) },
  );
  if (!respuesta.ok) throw new Error(`No se pudo descargar ${modelo.archivo}.`);
  const bytes = Buffer.from(await respuesta.arrayBuffer());
  if (
    bytes.length !== modelo.bytes ||
    createHash("sha256").update(bytes).digest("hex") !== modelo.sha256
  )
    throw new Error(`Integridad no válida: ${modelo.archivo}.`);
  const temporal = new URL(`${modelo.archivo}.partial`, destino);
  try {
    await writeFile(temporal, bytes);
    await rename(temporal, archivo);
  } finally {
    await rm(temporal, { force: true });
  }
  console.log(`${modelo.archivo}: descargado y verificado.`);
}
for (const modelo of manifiesto.modelos) {
  const respuesta = await fetch(
    `https://raw.githubusercontent.com/${manifiesto.repositorio}/${manifiesto.commit}/models/${modelo.carpeta}/LICENSE`,
  );
  if (!respuesta.ok)
    throw new Error("No se pudo obtener la licencia del modelo.");
  await writeFile(
    new URL(`${modelo.carpeta}.LICENSE`, destino),
    await respuesta.text(),
  );
}
