import base64
import binascii

from fastapi import APIRouter, Request

from ...api.dependencias import Accesos, Cuenta
from ...nucleo.errores import ErrorAplicacion
from .servicio import ServicioAsistente


def crear_rutas(voz_habilitada):
    rutas = APIRouter(prefix="/api/asistente")

    @rutas.post("/consulta")
    async def consultar(
        datos: dict, solicitud: Request, cuenta: Cuenta, accesos: Accesos
    ):
        return ServicioAsistente(accesos, solicitud.app.state.zona_horaria).consultar(
            datos.get("texto"), cuenta
        )

    if voz_habilitada:

        @rutas.post("/transcribir")
        async def transcribir(datos: dict, solicitud: Request, cuenta: Cuenta):
            try:
                audio = datos.get("audio")
                if not isinstance(audio, str) or len(audio) > ((256000 + 2) // 3) * 4:
                    raise ValueError()
                contenido = base64.b64decode(audio, validate=True)
                if not 3200 <= len(contenido) <= 256000 or len(contenido) % 2:
                    raise ValueError()
            except (ValueError, binascii.Error):
                raise ErrorAplicacion(
                    "Audio no válido. Grabe hasta 8 segundos."
                ) from None
            return {"texto": await solicitud.app.state.transcriptor.transcribir(audio)}

    return rutas
