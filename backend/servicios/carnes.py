import base64
import io
from uuid import uuid4

import qrcode

from ..nucleo.errores import ErrorAplicacion, nodos_no_disponibles
from ..nucleo.fechas import fecha_iso
from ..nucleo.validaciones import es_vector_facial_valido


class ServicioCarnes:
    def __init__(self, personas, nodos):
        self.personas = personas
        self.nodos = nodos

    async def obtener_referencia(self, foto):
        if not self.nodos:
            raise nodos_no_disponibles()
        resultado = await self.nodos.ejecutar_inferencia("registrar", {"foto": foto})
        if (
            not es_vector_facial_valido(resultado.get("vectorFacial"))
            or resultado.get("modelo") != "sface-2021dec"
        ):
            raise nodos_no_disponibles()
        return resultado

    async def registrar(self, datos, creador):
        referencia = await self.obtener_referencia(datos.foto)
        identificador = str(uuid4())
        self.personas.insertar(
            identificador,
            datos.nombres.strip(),
            datos.apellidos.strip(),
            datos.foto,
            referencia,
            fecha_iso(),
            creador,
        )
        return identificador

    def listar(self):
        return self.personas.listar()

    def obtener_persona(self, identificador):
        persona = self.personas.obtener_por_uuid(identificador)
        if not persona:
            raise ErrorAplicacion("Carné no encontrado.", 404)
        return persona

    def consultar(self, identificador):
        persona = self.obtener_persona(identificador)
        imagen = qrcode.make(persona["uuid"], border=4).resize((300, 300), resample=0)
        contenido = io.BytesIO()
        imagen.save(contenido, format="PNG")
        return {
            **{
                campo: persona[campo]
                for campo in (
                    "uuid",
                    "nombres",
                    "apellidos",
                    "foto",
                    "activo",
                    "fecha_creacion",
                )
            },
            "qr": "data:image/png;base64,"
            + base64.b64encode(contenido.getvalue()).decode(),
        }

    async def actualizar_foto(self, identificador, foto):
        self.obtener_persona(identificador)
        referencia = await self.obtener_referencia(foto)
        self.personas.actualizar_foto(identificador, foto, referencia)

    def cambiar_estado(self, identificador, activo):
        if not self.personas.cambiar_estado(identificador, activo):
            raise ErrorAplicacion("Carné no encontrado.", 404)
