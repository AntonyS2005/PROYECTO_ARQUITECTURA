import { rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const directorioPublico = fileURLToPath(new URL("../public", import.meta.url));
const recursos = resolve(directorioPublico, "assets");
if (dirname(recursos) !== directorioPublico)
  throw new Error("Directorio de compilación no válido.");
await rm(recursos, { recursive: true, force: true });
await build();
