import express from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import os from "node:os";
import { randomBytes, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import QRCode from "qrcode";
import { fileURLToPath } from "node:url";
import { validar } from "../public/validaciones.js";
import { ServicioAccesos } from "./servicio-accesos.js";
import {
  NodosNoDisponiblesError,
  esVectorFacialValido,
} from "./gestor-nodos.js";
import { permitirRedLocal } from "./red-local.js";
import { PATRON_UUID } from "../public/validaciones.js";
import { montarAsistente } from "../modulos/asistente/index.js";

const directorioPublico = fileURLToPath(new URL("../public/", import.meta.url));
const opcionesCookie = { httpOnly: true, sameSite: "strict", path: "/" };
const datosPublicosCuenta = ({ id, usuario, nombres, rol, activo }) => ({
  id,
  usuario,
  nombres,
  rol,
  activo: Boolean(activo),
});

export function crearAplicacion({
  baseDatos,
  claveInterna,
  nodo = os.hostname(),
  horasSesion = 8,
  minutosInactividad = 15,
  cookieSegura = false,
  nodos = null,
  umbralFacial = 0.363,
  asistenteHabilitado = false,
  transcribir = null,
}) {
  const aplicacion = express();
  const accesos = new ServicioAccesos(baseDatos);
  const modulos = {
    asistente: asistenteHabilitado,
    voz: asistenteHabilitado && Boolean(transcribir),
  };
  if (!Number.isFinite(umbralFacial) || umbralFacial < -1 || umbralFacial > 1)
    throw new Error("Umbral facial no válido.");
  const opciones = { ...opcionesCookie, secure: cookieSegura };
  const intentos = new Map();
  const segundosSesion = horasSesion * 3600;
  aplicacion.disable("x-powered-by");
  aplicacion.set("trust proxy", "loopback");
  aplicacion.use(permitirRedLocal);
  aplicacion.use((solicitud, respuesta, continuar) => {
    const nonce = randomBytes(16).toString("base64");
    respuesta.locals.nonce = nonce;
    respuesta.set({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "same-origin",
      "Content-Security-Policy": `default-src 'self'; script-src 'self'; style-src 'self' 'nonce-${nonce}'; style-src-attr 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
      "Permissions-Policy": `camera=(self), microphone=${modulos.voz ? "(self)" : "()"}`,
    });
    if (!["GET", "HEAD"].includes(solicitud.method)) {
      const esperado = `${solicitud.protocol}://${solicitud.get("host")}`;
      if (
        (solicitud.get("origin") && solicitud.get("origin") !== esperado) ||
        solicitud.get("sec-fetch-site") === "cross-site"
      )
        return respuesta
          .status(403)
          .json({ mensaje: "Solicitud no permitida." });
      if (!solicitud.is("application/json"))
        return respuesta
          .status(415)
          .json({ mensaje: "Formato de solicitud no válido." });
    }
    continuar();
  });
  aplicacion.use(express.json({ limit: "450kb" }));
  aplicacion.get(["/", "/index.html"], async (solicitud, respuesta) => {
    const pagina = await readFile(
      new URL("../public/index.html", import.meta.url),
      "utf8",
    );
    respuesta
      .type("html")
      .send(pagina.replace("__NONCE__", respuesta.locals.nonce));
  });
  aplicacion.use(express.static(directorioPublico));

  const validarSolicitud = (tipo) => (solicitud, respuesta, continuar) => {
    const errores = validar(tipo, solicitud.body ?? {});
    if (Object.keys(errores).length)
      return respuesta
        .status(422)
        .json({ mensaje: "Revise los campos indicados.", errores });
    continuar();
  };
  const obtenerReferenciaFacial = async (foto) => {
    if (!nodos) throw new NodosNoDisponiblesError();
    const resultado = await nodos.ejecutarInferencia("registrar", { foto });
    if (
      !esVectorFacialValido(resultado.vectorFacial) ||
      resultado.modelo !== "sface-2021dec"
    )
      throw new NodosNoDisponiblesError();
    return resultado;
  };
  const establecerSesion = (respuesta, cuenta, inicioSesion, vencimiento) => {
    const ahora = Math.floor(Date.now() / 1000);
    const token = jwt.sign(
      {
        sub: String(cuenta.id),
        version: cuenta.version,
        inicioSesion,
        ultimaActividad: ahora,
        exp: vencimiento,
      },
      claveInterna,
      {
        algorithm: "HS256",
        issuer: "control-acceso",
        audience: "terminal-local",
      },
    );
    respuesta.cookie("session", token, {
      ...opciones,
      maxAge: Math.max(0, vencimiento - ahora) * 1000,
    });
  };
  const autenticar = (solicitud, respuesta, continuar) => {
    try {
      const token = solicitud.headers.cookie
        ?.split(";")
        .map((elemento) => elemento.trim())
        .find((elemento) => elemento.startsWith("session="))
        ?.slice(8);
      const datosToken = jwt.verify(token, claveInterna, {
        algorithms: ["HS256"],
        issuer: "control-acceso",
        audience: "terminal-local",
      });
      const cuenta = baseDatos
        .prepare("SELECT * FROM usuarios WHERE id=?")
        .get(Number(datosToken.sub));
      if (
        !cuenta?.activo ||
        datosToken.version !== cuenta.version ||
        Date.now() / 1000 - datosToken.ultimaActividad >=
          minutosInactividad * 60
      )
        throw new Error("Sesión inactiva.");
      solicitud.cuenta = { ...cuenta, inicioSesion: datosToken.inicioSesion };
      establecerSesion(
        respuesta,
        cuenta,
        datosToken.inicioSesion,
        datosToken.exp,
      );
      continuar();
    } catch {
      respuesta.clearCookie("session", opciones);
      respuesta
        .status(401)
        .json({ mensaje: "Sesión finalizada. Inicie sesión." });
    }
  };
  const exigirAdministrador = (solicitud, respuesta, continuar) =>
    solicitud.cuenta.rol === "ADMINISTRADOR"
      ? continuar()
      : respuesta.status(403).json({ mensaje: "Acceso no autorizado." });
  const periodo = (solicitud, respuesta, continuar) => {
    const errores = validar("periodo", solicitud.query);
    if (Object.keys(errores).length)
      return respuesta
        .status(422)
        .json({ mensaje: "Revise las fechas indicadas.", errores });
    const inicio = new Date(`${solicitud.query.desde}T00:00:00`);
    const fin = new Date(`${solicitud.query.hasta}T00:00:00`);
    fin.setDate(fin.getDate() + 1);
    solicitud.periodo = {
      inicio: inicio.toISOString(),
      fin: fin.toISOString(),
    };
    continuar();
  };

  aplicacion.post(
    "/api/login",
    validarSolicitud("login"),
    async (solicitud, respuesta) => {
      const ahora = Date.now();
      for (const [clave, valor] of intentos)
        if (valor.hasta <= ahora) intentos.delete(clave);
      const intento = intentos.get(solicitud.ip) || {
        total: 0,
        hasta: ahora + 60000,
      };
      if (intento.total >= 8)
        return respuesta
          .status(429)
          .json({ mensaje: "Espere un minuto antes de intentar nuevamente." });
      intento.total++;
      intentos.set(solicitud.ip, intento);
      const cuenta = baseDatos
        .prepare("SELECT * FROM usuarios WHERE usuario=?")
        .get(solicitud.body.usuario);
      if (
        !cuenta?.activo ||
        !(await bcrypt.compare(solicitud.body.clave, cuenta.hash_clave))
      )
        return respuesta.status(401).json({
          mensaje: "Usuario o contraseña no válidos.",
          errores: {
            usuario: "Revise las credenciales.",
            clave: "Revise las credenciales.",
          },
        });
      intentos.delete(solicitud.ip);
      const inicioSesion = Math.floor(ahora / 1000);
      establecerSesion(
        respuesta,
        cuenta,
        inicioSesion,
        inicioSesion + segundosSesion,
      );
      respuesta.json({
        cuenta: datosPublicosCuenta(cuenta),
        minutosInactividad,
        modulos,
      });
    },
  );
  aplicacion.post("/api/logout", autenticar, (solicitud, respuesta) => {
    baseDatos
      .prepare("UPDATE usuarios SET version=version+1 WHERE id=?")
      .run(solicitud.cuenta.id);
    respuesta
      .clearCookie("session", opciones)
      .json({ mensaje: "Sesión finalizada." });
  });
  aplicacion.get("/api/me", autenticar, (solicitud, respuesta) =>
    respuesta.json({
      cuenta: datosPublicosCuenta(solicitud.cuenta),
      minutosInactividad,
      modulos,
    }),
  );
  aplicacion.post(
    "/api/carnes",
    autenticar,
    exigirAdministrador,
    validarSolicitud("carne"),
    async (solicitud, respuesta) => {
      const resultado = await obtenerReferenciaFacial(solicitud.body.foto);
      const uuid = randomUUID();
      baseDatos
        .prepare(
          `INSERT INTO personas(uuid,nombres,apellidos,foto,vector_facial,modelo,fecha_creacion,creado_por)
      VALUES(?,?,?,?,?,?,?,?)`,
        )
        .run(
          uuid,
          solicitud.body.nombres.trim(),
          solicitud.body.apellidos.trim(),
          solicitud.body.foto,
          JSON.stringify(resultado.vectorFacial),
          resultado.modelo,
          new Date().toISOString(),
          solicitud.cuenta.id,
        );
      respuesta.status(201).json({ mensaje: "Carné registrado.", uuid });
    },
  );
  aplicacion.get(
    "/api/carnes",
    autenticar,
    exigirAdministrador,
    (solicitud, respuesta) =>
      respuesta.json(
        baseDatos
          .prepare(
            "SELECT uuid,nombres,apellidos,activo,fecha_creacion FROM personas ORDER BY id DESC",
          )
          .all(),
      ),
  );
  aplicacion.get(
    "/api/carnes/:uuid",
    autenticar,
    exigirAdministrador,
    async (solicitud, respuesta) => {
      if (!PATRON_UUID.test(solicitud.params.uuid))
        return respuesta
          .status(422)
          .json({ mensaje: "Identificador de carné no válido." });
      const persona = baseDatos
        .prepare(
          "SELECT uuid,nombres,apellidos,foto,activo,fecha_creacion FROM personas WHERE uuid=?",
        )
        .get(solicitud.params.uuid.toLowerCase());
      if (!persona)
        return respuesta.status(404).json({ mensaje: "Carné no encontrado." });
      respuesta.json({
        ...persona,
        qr: await QRCode.toDataURL(persona.uuid, { width: 300, margin: 4 }),
      });
    },
  );
  aplicacion.patch(
    "/api/carnes/:uuid/foto",
    autenticar,
    exigirAdministrador,
    validarSolicitud("fotografia"),
    async (solicitud, respuesta) => {
      if (!PATRON_UUID.test(solicitud.params.uuid))
        return respuesta
          .status(422)
          .json({ mensaje: "Identificador de carné no válido." });
      const uuid = solicitud.params.uuid.toLowerCase();
      if (!baseDatos.prepare("SELECT id FROM personas WHERE uuid=?").get(uuid))
        return respuesta.status(404).json({ mensaje: "Carné no encontrado." });
      const resultado = await obtenerReferenciaFacial(solicitud.body.foto);
      baseDatos
        .prepare(
          "UPDATE personas SET foto=?,vector_facial=?,modelo=? WHERE uuid=?",
        )
        .run(
          solicitud.body.foto,
          JSON.stringify(resultado.vectorFacial),
          resultado.modelo,
          uuid,
        );
      respuesta.json({ mensaje: "Fotografía actualizada.", uuid });
    },
  );
  aplicacion.patch(
    "/api/carnes/:uuid",
    autenticar,
    exigirAdministrador,
    (solicitud, respuesta) => {
      if (
        !PATRON_UUID.test(solicitud.params.uuid) ||
        typeof solicitud.body.activo !== "boolean"
      )
        return respuesta.status(422).json({ mensaje: "Datos no válidos." });
      const resultado = baseDatos
        .prepare("UPDATE personas SET activo=? WHERE uuid=?")
        .run(
          Number(solicitud.body.activo),
          solicitud.params.uuid.toLowerCase(),
        );
      if (!resultado.changes)
        return respuesta.status(404).json({ mensaje: "Carné no encontrado." });
      respuesta.json({
        mensaje: solicitud.body.activo
          ? "Carné activado."
          : "Carné desactivado.",
      });
    },
  );
  aplicacion.post(
    "/api/accesos",
    autenticar,
    validarSolicitud("acceso"),
    async (solicitud, respuesta) => {
      if (!nodos) throw new NodosNoDisponiblesError();
      const lectura = await nodos.ejecutarInferencia("leer-carne", {
        foto: solicitud.body.fotoCarne,
      });
      const persona = baseDatos
        .prepare("SELECT * FROM personas WHERE uuid=? AND activo=1")
        .get(lectura.uuid.toLowerCase());
      if (!persona)
        return respuesta.status(422).json({
          mensaje: "Carné no disponible.",
          errores: {
            fotoCarne: "El carné no está registrado o está desactivado.",
          },
        });
      const resultado = await nodos.ejecutarInferencia("verificar", {
        foto: solicitud.body.foto,
        umbral: umbralFacial,
        vectorFacial: JSON.parse(persona.vector_facial),
      });
      if (resultado.modelo !== persona.modelo)
        throw new NodosNoDisponiblesError();
      const evento = accesos.registrarAcceso(
        persona,
        { ...resultado, umbral: umbralFacial },
        solicitud.cuenta.id,
      );
      respuesta.status(201).json({
        evento,
        mensaje:
          evento.estado === "RECHAZADO"
            ? "Verificación no aprobada."
            : `${evento.tipo === "ENTRADA" ? "Entrada" : "Salida"} registrada.`,
      });
    },
  );
  aplicacion.get(
    "/api/eventos",
    autenticar,
    (solicitud, respuesta, continuar) =>
      solicitud.cuenta.rol === "OPERADOR"
        ? continuar()
        : periodo(solicitud, respuesta, continuar),
    (solicitud, respuesta) =>
      respuesta.json(
        accesos.consultarHistorial(solicitud.cuenta, solicitud.periodo),
      ),
  );
  aplicacion.get(
    "/api/eventos/:id/foto",
    autenticar,
    exigirAdministrador,
    (solicitud, respuesta) => {
      const id = Number(solicitud.params.id);
      if (!Number.isSafeInteger(id) || id < 1)
        return respuesta
          .status(422)
          .json({ mensaje: "Identificador no válido." });
      const captura = baseDatos
        .prepare(
          "SELECT f.foto FROM fotografias_rechazos f JOIN eventos e ON e.id=f.evento_id WHERE e.id=? AND e.estado='RECHAZADO'",
        )
        .get(id);
      if (!captura)
        return respuesta
          .status(404)
          .json({ mensaje: "Fotografía no disponible." });
      respuesta.type("image/webp").send(Buffer.from(captura.foto));
    },
  );
  aplicacion.get(
    "/api/metricas",
    autenticar,
    exigirAdministrador,
    periodo,
    (solicitud, respuesta) =>
      respuesta.json(accesos.consultarMetricas(solicitud.periodo)),
  );
  aplicacion.get(
    "/api/exportar",
    autenticar,
    exigirAdministrador,
    periodo,
    (solicitud, respuesta) => {
      const columnas = [
        "uuid",
        "nombres",
        "apellidos",
        "tipo",
        "estado",
        "similitud",
        "umbral",
        "modelo",
        "fecha_hora",
        "nodo",
        "usuario",
      ];
      const escaparCsv = (valor) =>
        `"${String(valor ?? "")
          .replace(/^[=+@-]/, "'$&")
          .replaceAll('"', '""')}"`;
      const contenidoCsv = [
        columnas,
        ...accesos
          .consultarHistorial(solicitud.cuenta, solicitud.periodo)
          .map((evento) => columnas.map((clave) => evento[clave])),
      ]
        .map((fila) => fila.map(escaparCsv).join(","))
        .join("\r\n");
      respuesta
        .attachment("reporte-accesos.csv")
        .type("text/csv; charset=utf-8")
        .send("\uFEFF" + contenidoCsv);
    },
  );
  aplicacion.get(
    "/api/cuentas",
    autenticar,
    exigirAdministrador,
    (solicitud, respuesta) =>
      respuesta.json(
        baseDatos
          .prepare(
            "SELECT id,usuario,nombres,rol,activo FROM usuarios ORDER BY id",
          )
          .all()
          .map(datosPublicosCuenta),
      ),
  );
  aplicacion.post(
    "/api/cuentas",
    autenticar,
    exigirAdministrador,
    validarSolicitud("cuenta"),
    async (solicitud, respuesta) => {
      const { usuario, clave, nombres, rol } = solicitud.body;
      const hashClave = await bcrypt.hash(clave, 10);
      try {
        baseDatos
          .prepare(
            "INSERT INTO usuarios(usuario,hash_clave,nombres,rol) VALUES(?,?,?,?)",
          )
          .run(usuario, hashClave, nombres.trim(), rol);
        respuesta.status(201).json({ mensaje: "Cuenta registrada." });
      } catch (error) {
        if (error.message.includes("UNIQUE"))
          return respuesta.status(409).json({
            mensaje: "El usuario ya está registrado.",
            errores: { usuario: "El usuario ya está registrado." },
          });
        throw error;
      }
    },
  );
  aplicacion.patch(
    "/api/cuentas/:id",
    autenticar,
    exigirAdministrador,
    (solicitud, respuesta) => {
      const id = Number(solicitud.params.id);
      if (
        !Number.isSafeInteger(id) ||
        id < 1 ||
        typeof solicitud.body.activo !== "boolean"
      )
        return respuesta.status(422).json({ mensaje: "Datos no válidos." });
      if (id === solicitud.cuenta.id)
        return respuesta
          .status(409)
          .json({ mensaje: "No se puede desactivar la cuenta en uso." });
      const resultado = baseDatos
        .prepare("UPDATE usuarios SET activo=?, version=version+1 WHERE id=?")
        .run(Number(solicitud.body.activo), id);
      if (!resultado.changes)
        return respuesta.status(404).json({ mensaje: "Cuenta no encontrada." });
      respuesta.json({
        mensaje: solicitud.body.activo
          ? "Cuenta activada."
          : "Cuenta desactivada.",
      });
    },
  );
  aplicacion.get(
    "/api/nodo",
    autenticar,
    exigirAdministrador,
    async (solicitud, respuesta) =>
      respuesta.json({
        nombre: nodo,
        tiempoActivoSegundos: Math.floor(process.uptime()),
        memoriaMb: Math.round(process.memoryUsage().rss / 1024 / 1024),
        modo: "Clúster local · Carnés",
        baseDatos: "SQLite",
        nodos: nodos ? await nodos.consultarEstado() : [],
      }),
  );
  if (asistenteHabilitado)
    montarAsistente(aplicacion, { autenticar, accesos, transcribir });
  aplicacion.use("/api", (solicitud, respuesta) =>
    respuesta.status(404).json({ mensaje: "Recurso no encontrado." }),
  );
  aplicacion.use((error, solicitud, respuesta, continuar) => {
    if ([409, 422, 503].includes(error.status))
      return respuesta.status(error.status).json({
        mensaje: error.message,
        ...(error.codigo ? { codigo: error.codigo } : {}),
        ...(error.errores ? { errores: error.errores } : {}),
      });
    if (error.type === "entity.parse.failed")
      return respuesta
        .status(400)
        .json({ mensaje: "Formato de solicitud no válido." });
    if (error.type === "entity.too.large")
      return respuesta
        .status(413)
        .json({ mensaje: "La solicitud supera el tamaño permitido." });
    console.error("Error interno:", error.message);
    respuesta
      .status(500)
      .json({ mensaje: "No se pudo completar la operación." });
  });
  return aplicacion;
}
