export const LIMITE_TEXTO = 200;
export const LIMITE_AUDIO = 256000;

export function validarConsulta(texto) {
  return typeof texto !== "string" || !texto.trim()
    ? { texto: "Ingrese una consulta." }
    : texto.length > LIMITE_TEXTO
      ? { texto: `Máximo ${LIMITE_TEXTO} caracteres.` }
      : {};
}

export function esAudioValido(audio) {
  if (
    typeof audio !== "string" ||
    !audio.length ||
    audio.length > Math.ceil(LIMITE_AUDIO / 3) * 4
  )
    return false;
  if (
    !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(
      audio,
    )
  )
    return false;
  const tamano =
    (audio.length / 4) * 3 -
    (audio.endsWith("==") ? 2 : audio.endsWith("=") ? 1 : 0);
  return tamano >= 3200 && tamano <= LIMITE_AUDIO && tamano % 2 === 0;
}

const intenciones = new Map([
  ["ayuda", { tipo: "ayuda" }],
  ["abrir registro", { tipo: "navegar", vista: "operacion" }],
  [
    "abrir carnes",
    { tipo: "navegar", vista: "carnes", soloAdministrador: true },
  ],
  [
    "abrir reportes",
    { tipo: "navegar", vista: "reportes", soloAdministrador: true },
  ],
  [
    "estado de los nodos",
    { tipo: "navegar", vista: "nodo", soloAdministrador: true },
  ],
  ["capturar foto", { tipo: "capturar" }],
  ["cuantas personas hay dentro", { tipo: "aforo", soloAdministrador: true }],
  [
    "mostrar las entradas de hoy",
    { tipo: "entradas", soloAdministrador: true },
  ],
  ["cuantas entradas hubo hoy", { tipo: "entradas", soloAdministrador: true }],
]);

export function identificarIntencion(texto) {
  const normalizado = texto
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[¿?¡!.,]/g, "")
    .trim()
    .replace(/\s+/g, " ");
  return intenciones.get(normalizado) || null;
}
