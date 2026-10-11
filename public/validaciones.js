export const limites = {
  usuario: 30,
  clave: 64,
  nombres: 100,
  apellidos: 100,
  uuid: 36,
};

export const MAXIMO_CARACTERES_FOTO = 400000;
export const PATRON_UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function validar(tipo, valores) {
  const errores = {};
  const texto = (clave, minimo, maximo, patron, mensaje) => {
    const original = valores[clave];
    const valor =
      typeof original === "string" && ["nombres", "apellidos"].includes(clave)
        ? original.trim()
        : original;
    if (typeof valor !== "string" || !valor.trim())
      errores[clave] = "Campo obligatorio.";
    else if (valor.length < minimo || valor.length > maximo)
      errores[clave] = `Debe contener entre ${minimo} y ${maximo} caracteres.`;
    else if (patron && !patron.test(valor)) errores[clave] = mensaje;
  };
  if (tipo === "login" || tipo === "cuenta") {
    texto(
      "usuario",
      3,
      limites.usuario,
      /^[a-zA-Z0-9._-]+$/,
      "Solo letras, números, punto, guion y guion bajo.",
    );
    texto("clave", tipo === "cuenta" ? 8 : 1, limites.clave);
    if (
      typeof valores.clave === "string" &&
      new TextEncoder().encode(valores.clave).length > 72
    )
      errores.clave = "La contraseña supera el límite de 72 bytes.";
  }
  if (tipo === "carne" || tipo === "cuenta") {
    for (const clave of ["nombres", ...(tipo === "carne" ? ["apellidos"] : [])])
      texto(
        clave,
        2,
        limites[clave],
        /^[\p{L}\p{M} .'-]+$/u,
        "Solo letras, espacios, punto, apóstrofo y guion.",
      );
  }
  if (["acceso", "carne", "fotografia"].includes(tipo)) {
    for (const campo of tipo === "acceso" ? ["foto", "fotoCarne"] : ["foto"]) {
      const foto = valores[campo];
      if (!foto)
        errores[campo] =
          tipo === "acceso"
            ? "Capture el rostro y el carné antes de continuar."
            : "Seleccione una fotografía.";
      else if (typeof foto !== "string" || foto.length > MAXIMO_CARACTERES_FOTO)
        errores[campo] = "La fotografía supera el tamaño permitido.";
      else if (!/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(foto))
        errores[campo] = "Se requiere una fotografía JPEG válida.";
      else {
        try {
          const bytes = atob(foto.slice(23));
          if (
            bytes.length < 6 ||
            !bytes.startsWith("\xff\xd8\xff") ||
            !bytes.endsWith("\xff\xd9")
          )
            errores[campo] = "Se requiere una fotografía JPEG válida.";
        } catch {
          errores[campo] = "Se requiere una fotografía JPEG válida.";
        }
      }
    }
    if (
      tipo === "acceso" &&
      typeof valores.foto === "string" &&
      typeof valores.fotoCarne === "string" &&
      valores.foto.length + valores.fotoCarne.length > MAXIMO_CARACTERES_FOTO
    )
      errores.foto =
        "La captura supera el tamaño permitido. Intente nuevamente.";
  }
  if (tipo === "cuenta" && !["ADMINISTRADOR", "OPERADOR"].includes(valores.rol))
    errores.rol = "Seleccione un rol válido.";
  if (tipo === "periodo") {
    for (const clave of ["desde", "hasta"]) {
      const valor = valores[clave];
      if (
        typeof valor !== "string" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(valor) ||
        !Number.isFinite(Date.parse(valor)) ||
        new Date(valor).toISOString().slice(0, 10) !== valor
      )
        errores[clave] = "Seleccione una fecha válida.";
    }
    if (!Object.keys(errores).length && valores.desde > valores.hasta)
      errores.hasta = "Debe ser igual o posterior a la fecha inicial.";
  }
  return errores;
}
