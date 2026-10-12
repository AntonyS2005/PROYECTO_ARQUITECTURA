import { MAXIMO_CARACTERES_FOTO } from "../../public/validaciones.js";

function recortarImagen(
  origen,
  ancho,
  alto,
  { inicio = 0, proporcion = 1, maximo = 640 } = {},
  lienzo = document.createElement("canvas"),
) {
  const anchoRecorte = Math.round(ancho * proporcion);
  const escala = Math.min(1, maximo / Math.max(anchoRecorte, alto));
  const anchoFinal = Math.round(anchoRecorte * escala);
  const altoFinal = Math.round(alto * escala);
  if (lienzo.width !== anchoFinal) lienzo.width = anchoFinal;
  if (lienzo.height !== altoFinal) lienzo.height = altoFinal;
  lienzo
    .getContext("2d")
    .drawImage(
      origen,
      Math.round(ancho * inicio),
      0,
      anchoRecorte,
      alto,
      0,
      0,
      lienzo.width,
      lienzo.height,
    );
  return lienzo;
}

export function capturarJpeg(origen, ancho, alto, opciones = {}) {
  return recortarImagen(origen, ancho, alto, opciones).toDataURL(
    "image/jpeg",
    opciones.calidad ?? 0.82,
  );
}

export function crearCaptura() {
  const fotograma = document.createElement("canvas");
  const rostro = document.createElement("canvas");
  const carne = document.createElement("canvas");

  function obtener(camara) {
    if (fotograma.width !== camara.videoWidth) fotograma.width = camara.videoWidth;
    if (fotograma.height !== camara.videoHeight)
      fotograma.height = camara.videoHeight;
    fotograma.getContext("2d").drawImage(camara, 0, 0);
    recortarImagen(
      fotograma,
      fotograma.width,
      fotograma.height,
      { inicio: 0.35, proporcion: 0.65 },
      rostro,
    );
    recortarImagen(
      fotograma,
      fotograma.width,
      fotograma.height,
      { proporcion: 0.35, maximo: 960 },
      carne,
    );
    let foto = rostro.toDataURL("image/jpeg", 0.82);
    let fotoCarne = carne.toDataURL("image/jpeg", 0.92);
    if (foto.length + fotoCarne.length > MAXIMO_CARACTERES_FOTO) {
      foto = rostro.toDataURL("image/jpeg", 0.65);
      fotoCarne = carne.toDataURL("image/jpeg", 0.82);
    }
    return { foto, fotoCarne };
  }

  function cerrar() {
    for (const lienzo of [fotograma, rostro, carne])
      lienzo.width = lienzo.height = 0;
  }

  return { obtener, cerrar };
}

export async function normalizarFoto(archivo) {
  if (
    !["image/jpeg", "image/png"].includes(archivo.type) ||
    archivo.size > 5 * 1024 * 1024
  )
    throw new Error("Seleccione un JPEG o PNG de hasta 5 MB.");
  const imagen = await createImageBitmap(archivo);
  try {
    if (
      imagen.width < 80 ||
      imagen.height < 80 ||
      imagen.width * imagen.height > 24000000
    )
      throw new Error(
        "La fotografía debe tener al menos 80 × 80 píxeles y máximo 24 megapíxeles.",
      );
    return capturarJpeg(imagen, imagen.width, imagen.height);
  } finally {
    imagen.close();
  }
}
