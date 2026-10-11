class ErrorAplicacion(Exception):
    def __init__(self, mensaje, estado=422, errores=None, codigo=None):
        super().__init__(mensaje)
        self.estado = estado
        self.contenido = {"mensaje": mensaje}
        if errores:
            self.contenido["errores"] = errores
        if codigo:
            self.contenido["codigo"] = codigo
