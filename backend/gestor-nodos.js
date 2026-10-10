import jwt from "jsonwebtoken";
import { PATRON_UUID } from "../public/validaciones.js";
import { decodificarFotoRechazo } from "./fotografias-rechazos.js";

export class NodosNoDisponiblesError extends Error {
  constructor() {
    super("No hay nodos de verificación disponibles. Intente nuevamente.");
    this.status = 503;
  }
}

export class GestorNodos {
  constructor(nodos, claveInterna, esperaMs = 5000) {
    if (
      !Array.isArray(nodos) ||
      nodos.length < 1 ||
      nodos.length > 8 ||
      new Set(nodos.map((nodo) => nodo.id)).size !== nodos.length
    )
      throw new Error(
        "Configure entre uno y ocho workers con identificadores únicos.",
      );
    this.nodos = nodos.map((nodo) => {
      const url = new URL(nodo.url);
      if (
        !/^[a-zA-Z0-9_-]{1,50}$/.test(nodo.id) ||
        url.protocol !== "http:" ||
        url.username ||
        url.password ||
        url.pathname !== "/" ||
        url.search ||
        url.hash ||
        !/^(127\.0\.0\.1|192\.168\.50\.\d{1,3})$/.test(url.hostname) ||
        url.hostname.split(".").some((segmento) => Number(segmento) > 255)
      )
        throw new Error("Worker fuera de la red local permitida.");
      return { id: nodo.id, url: url.origin };
    });
    if (
      typeof claveInterna !== "string" ||
      claveInterna.length < 32 ||
      !Number.isInteger(esperaMs) ||
      esperaMs < 100 ||
      esperaMs > 30000
    )
      throw new Error("Clave de workers o tiempo de espera no válido.");
    this.claveInterna = claveInterna;
    this.esperaMs = esperaMs;
    this.indiceActual = 0;
  }

  async solicitar(nodo, ruta, contenido) {
    const token = jwt.sign(
      { scope: ruta === "/health" ? "health" : "inference" },
      this.claveInterna,
      {
        algorithm: "HS256",
        issuer: "edge-master",
        audience: nodo.id,
        expiresIn: 30,
      },
    );
    const respuesta = await fetch(`${nodo.url}${ruta}`, {
      method: contenido ? "POST" : "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(contenido ? { "Content-Type": "application/json" } : {}),
      },
      body: contenido ? JSON.stringify(contenido) : undefined,
      redirect: "error",
      signal: AbortSignal.timeout(this.esperaMs),
    });
    const lector = respuesta.body.getReader();
    let longitud = 0;
    const fragmentos = [];
    try {
      while (true) {
        const { done, value: valor } = await lector.read();
        if (done) break;
        longitud += valor.length;
        if (longitud > 24000)
          throw new Error("Respuesta de worker demasiado grande.");
        fragmentos.push(Buffer.from(valor));
      }
    } finally {
      await lector.cancel();
    }
    const datos = JSON.parse(Buffer.concat(fragmentos).toString("utf8"));
    const mensajeFotografia =
      {
        ROSTRO_NO_DETECTADO:
          "No se detectó el rostro. Use una fotografía de frente y con buena iluminación.",
        VARIOS_ROSTROS:
          "Se detectó más de un rostro. Use una fotografía individual.",
        FOTO_NO_VALIDA:
          "No se pudo leer la fotografía. Seleccione otro archivo.",
      }[datos.codigo] ||
      "No se pudo procesar el rostro. Use una fotografía clara con una sola persona.";
    if (respuesta.status === 422)
      throw Object.assign(
        new Error(
          contenido?.operacion === "leer-carne"
            ? "No se pudo leer el carné."
            : mensajeFotografia,
        ),
        {
          status: 422,
          codigo:
            contenido?.operacion === "leer-carne"
              ? "QR_NO_LEIBLE"
              : datos.codigo,
          errores:
            contenido?.operacion === "leer-carne"
              ? {
                  fotoCarne:
                    "Coloque el QR del carné dentro del área indicada.",
                }
              : {
                  foto: mensajeFotografia,
                },
        },
      );
    if (!respuesta.ok || datos.nodo !== nodo.id)
      throw new Error("Worker no disponible.");
    return datos;
  }

  async ejecutarInferencia(operacion, contenido) {
    if (!["registrar", "verificar", "leer-carne"].includes(operacion))
      throw new Error("Operación no válida.");
    const inicio = this.indiceActual++ % this.nodos.length;
    for (
      let desplazamiento = 0;
      desplazamiento < this.nodos.length;
      desplazamiento++
    ) {
      const nodo = this.nodos[(inicio + desplazamiento) % this.nodos.length];
      try {
        const datos = await this.solicitar(nodo, "/infer", {
          ...contenido,
          operacion,
        });
        if (
          datos.modelo !== "sface-2021dec" ||
          (operacion === "leer-carne"
            ? typeof datos.uuid !== "string" || !PATRON_UUID.test(datos.uuid)
            : operacion === "registrar"
              ? !esVectorFacialValido(datos.vectorFacial)
              : typeof datos.similitud !== "number" ||
                !Number.isFinite(datos.similitud) ||
                datos.similitud < -1 ||
                datos.similitud > 1)
        )
          throw new Error("Resultado de inferencia no válido.");
        if (
          operacion === "verificar" &&
          datos.similitud < (contenido.umbral ?? 0.363) &&
          !decodificarFotoRechazo(datos.fotoRechazo)
        )
          throw new Error("Captura de rechazo ausente.");
        return datos;
      } catch (error) {
        if (error.status === 422) throw error;
      }
    }
    throw new NodosNoDisponiblesError();
  }

  async consultarEstado() {
    return Promise.all(
      this.nodos.map(async (nodo) => {
        const inicio = performance.now();
        try {
          const datos = await this.solicitar(nodo, "/health");
          if (datos.modelo !== "sface-2021dec")
            throw new Error("Modelo de worker no válido.");
          return {
            id: nodo.id,
            status: "En línea",
            latenciaMs: Math.round(performance.now() - inicio),
            modelo: datos.modelo,
          };
        } catch {
          return {
            id: nodo.id,
            status: "Sin respuesta",
            latenciaMs: null,
            modelo: null,
          };
        }
      }),
    );
  }
}

export function esVectorFacialValido(valor) {
  if (
    !Array.isArray(valor) ||
    valor.length !== 128 ||
    valor.some(
      (componente) =>
        typeof componente !== "number" ||
        !Number.isFinite(componente) ||
        Math.abs(componente) > 1.001,
    )
  )
    return false;
  const norma = Math.sqrt(
    valor.reduce((suma, componente) => suma + componente ** 2, 0),
  );
  return norma > 0.99 && norma < 1.01;
}
