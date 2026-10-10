import { spawn } from "node:child_process";
import { mkdir, readFile, rename, writeFile, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const directorioRaiz = fileURLToPath(new URL("../", import.meta.url));
const destino = join(directorioRaiz, "artifacts");
const manifiesto = JSON.parse(
  await readFile(join(directorioRaiz, "worker/modelos.json"), "utf8"),
);
for (const modelo of manifiesto.modelos) {
  const bytes = await readFile(
    join(directorioRaiz, "worker/modelos", modelo.archivo),
  );
  if (
    bytes.length !== modelo.bytes ||
    createHash("sha256").update(bytes).digest("hex") !== modelo.sha256
  )
    throw new Error(
      `Modelo no válido: ${modelo.archivo}. Ejecute npm run modelos:descargar.`,
    );
}
await mkdir(destino, { recursive: true });
const temporal = join(destino, "edge-access.tar.gz.partial");
const paquete = join(destino, "edge-access.tar.gz");
try {
  const proceso = spawn(
    "tar",
    [
      "-czf",
      temporal,
      "--exclude=__pycache__",
      "--exclude=.venv",
      "src",
      "public",
      "frontend",
      "vite.config.js",
      "worker",
      "modulos",
      "deploy",
      "scripts",
      "package.json",
      "package-lock.json",
    ],
    { cwd: directorioRaiz, windowsHide: true, stdio: "inherit" },
  );
  await new Promise((resolver, rechazar) => {
    proceso.once("error", rechazar);
    proceso.once("exit", (codigoSalida) =>
      codigoSalida === 0
        ? resolver()
        : rechazar(new Error("No se pudo preparar el paquete.")),
    );
  });
  await rename(temporal, paquete);
  const hashClave = createHash("sha256")
    .update(await readFile(paquete))
    .digest("hex");
  await writeFile(
    join(destino, "edge-access.tar.gz.sha256"),
    `${hashClave}  edge-access.tar.gz\n`,
  );
  console.log(`Paquete generado: ${paquete}`);
} finally {
  await rm(temporal, { force: true });
}
