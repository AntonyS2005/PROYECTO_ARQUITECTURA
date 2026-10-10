import { mkdirSync, existsSync, writeFileSync, readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";
import { abrirBaseDatos } from "./base-datos.js";
import { crearAplicacion } from "./aplicacion.js";
import { GestorNodos } from "./gestor-nodos.js";
import { crearTranscriptor } from "./modulos/asistente/cliente-voz.js";

const directorio = fileURLToPath(new URL("../data/", import.meta.url));
mkdirSync(directorio, { recursive: true });
const rutaClave = `${directorio}/session.key`;
if (!existsSync(rutaClave))
  writeFileSync(rutaClave, randomBytes(48).toString("hex"), { mode: 0o600 });
const claveInterna =
  process.env.CLAVE_SESION || readFileSync(rutaClave, "utf8");
if (claveInterna.length < 32)
  throw new Error("CLAVE_SESION requiere al menos 32 caracteres.");
const baseDatos = abrirBaseDatos(`${directorio}/access.sqlite`);
const horas = Number(process.env.HORAS_SESION || 8);
const inactividad = Number(process.env.MINUTOS_INACTIVIDAD || 15);
if (![horas, inactividad].every((valor) => Number.isFinite(valor) && valor > 0))
  throw new Error("La duración de sesión debe ser positiva.");
const aplicacion = crearAplicacion({
  baseDatos,
  asistenteHabilitado: process.env.ASISTENTE_HABILITADO === "true",
  transcribir:
    process.env.ASISTENTE_HABILITADO === "true" &&
    process.env.VOZ_HABILITADA === "true"
      ? crearTranscriptor(process.env.CLAVE_VOZ)
      : null,
  claveInterna,
  horasSesion: horas,
  minutosInactividad: inactividad,
  cookieSegura: process.env.COOKIE_SEGURA === "true",
  nodos: process.env.NODOS
    ? new GestorNodos(
        JSON.parse(process.env.NODOS),
        process.env.CLAVE_NODOS,
        Number(process.env.ESPERA_NODOS_MS || 5000),
      )
    : null,
  umbralFacial: Number(process.env.UMBRAL_FACIAL || 0.363),
});
const puerto = Number(process.env.PORT || 3000);
const direccionEscucha = process.env.HOST || "127.0.0.1";
if (!["127.0.0.1", "192.168.50.10", "0.0.0.0"].includes(direccionEscucha))
  throw new Error("HOST no corresponde al montaje local.");
const servidor = aplicacion.listen(puerto, direccionEscucha, () =>
  console.log(`Control de acceso: http://${direccionEscucha}:${puerto}`),
);
for (const senal of ["SIGINT", "SIGTERM"])
  process.on(senal, () =>
    servidor.close(() => {
      baseDatos.close();
      process.exit(0);
    }),
  );
