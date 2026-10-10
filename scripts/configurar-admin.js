import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import bcrypt from "bcryptjs";
import { abrirBaseDatos } from "../src/base-datos.js";
import { validar } from "../public/validaciones.js";

const directorio = fileURLToPath(new URL("../data/", import.meta.url));
mkdirSync(directorio, { recursive: true });
const baseDatos = abrirBaseDatos(`${directorio}/access.sqlite`);
const usuario = process.env.USUARIO_ADMIN || "admin";
const clave = process.env.CLAVE_ADMIN;
const valores = {
  usuario,
  clave,
  nombres: "Administración",
  rol: "ADMINISTRADOR",
};
const errores = validar("cuenta", valores);
if (Object.keys(errores).length) {
  console.error("Defina CLAVE_ADMIN con 8 a 64 caracteres (máximo 72 bytes).");
  baseDatos.close();
  process.exitCode = 1;
} else if (
  baseDatos.prepare("SELECT id FROM usuarios WHERE usuario=?").get(usuario)
) {
  console.log("La cuenta ya existe. No se realizaron cambios.");
  baseDatos.close();
} else {
  baseDatos
    .prepare(
      "INSERT INTO usuarios(usuario,hash_clave,nombres,rol) VALUES(?,?,?,?)",
    )
    .run(usuario, await bcrypt.hash(clave, 10), valores.nombres, valores.rol);
  console.log("Cuenta administrativa registrada.");
  baseDatos.close();
}
