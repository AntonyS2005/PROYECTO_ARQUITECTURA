import { MAXIMO_CARACTERES_FOTO } from "../../public/validaciones.js";

export function capturarJpeg(
  origen,
  ancho,
  alto,
  { inicio = 0, proporcion = 1, maximo = 640, calidad = 0.82 } = {},
) {
  const anchoRecorte = Math.round(ancho * proporcion);
  const escala = Math.min(1, maximo / Math.max(anchoRecorte, alto));
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.round(anchoRecorte * escala);
  lienzo.height = Math.round(alto * escala);
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
  return lienzo.toDataURL("image/jpeg", calidad);
}

export function obtenerCaptura(camara) {
  const captura = document.createElement("canvas");
  captura.width = camara.videoWidth;
  captura.height = camara.videoHeight;
  captura.getContext("2d").drawImage(camara, 0, 0);
  const foto = capturarJpeg(captura, captura.width, captura.height, {
    inicio: 0.35,
    proporcion: 0.65,
  });
  let fotoCarne = capturarJpeg(captura, captura.width, captura.height, {
    proporcion: 0.35,
    maximo: 960,
    calidad: 0.92,
  });
  if (foto.length + fotoCarne.length > MAXIMO_CARACTERES_FOTO)
    fotoCarne = capturarJpeg(captura, captura.width, captura.height, {
      proporcion: 0.35,
      maximo: 960,
      calidad: 0.75,
    });
  return { foto, fotoCarne };
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
