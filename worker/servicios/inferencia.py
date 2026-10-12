import numpy as np

from ..nucleo.validaciones import validar_operacion, validar_referencia


class ServicioInferencia:
    def __init__(self, motor, decodificar_foto, generar_miniatura):
        self.motor = motor
        self.decodificar_foto = decodificar_foto
        self.generar_miniatura = generar_miniatura

    def inferir(self, cuerpo):
        operacion = validar_operacion(cuerpo)
        if operacion == "leer-carne":
            return self.motor.leer_carne(self.decodificar_foto(cuerpo.get("foto")))
        referencia, umbral = (
            validar_referencia(cuerpo) if operacion == "verificar" else (None, None)
        )
        imagen = self.decodificar_foto(cuerpo.get("foto"))
        vector = self.motor.extraer_vector(imagen)
        if referencia is None:
            return {"vectorFacial": vector.tolist()}
        similitud = float(np.clip(np.dot(vector, referencia), -1, 1))
        resultado = {"similitud": similitud}
        if similitud < umbral:
            resultado["fotoRechazo"] = self.generar_miniatura(imagen)
        return resultado
