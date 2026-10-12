from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from ..nucleo.errores import ErrorAplicacion
from ..nucleo.validaciones import validar


class EntradaValidada(BaseModel):
    model_config = ConfigDict(strict=True)
    tipo: ClassVar[str]

    @model_validator(mode="before")
    @classmethod
    def revisar(cls, valores):
        if not isinstance(valores, dict):
            raise ErrorAplicacion("Formato de solicitud no válido.", 400)
        errores = validar(cls.tipo, valores)
        if errores:
            raise ErrorAplicacion("Revise los campos indicados.", errores=errores)
        return valores


class InicioSesion(EntradaValidada):
    tipo = "login"
    usuario: str
    clave: str


class CuentaNueva(InicioSesion):
    tipo = "cuenta"
    nombres: str
    rol: str


class Fotografia(EntradaValidada):
    tipo = "fotografia"
    foto: str


class CarneNuevo(Fotografia):
    tipo = "carne"
    nombres: str
    apellidos: str


class CapturaAcceso(Fotografia):
    tipo = "acceso"
    fotoCarne: str


class CambioEstado(BaseModel):
    model_config = ConfigDict(strict=True)
    activo: bool
