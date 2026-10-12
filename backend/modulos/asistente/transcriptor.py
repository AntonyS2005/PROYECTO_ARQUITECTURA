import json

import httpx

from ...nucleo.errores import ErrorAplicacion
from .servicio import validar_consulta


class Transcriptor:
    def __init__(self, clave):
        self.clave = clave
        self.ocupado = False
        self.cliente = httpx.AsyncClient(
            timeout=15, trust_env=False, follow_redirects=False
        )

    async def cerrar(self):
        await self.cliente.aclose()

    async def transcribir(self, audio):
        if self.ocupado:
            raise ErrorAplicacion("Reconocimiento ocupado. Intente nuevamente.", 503)
        self.ocupado = True
        try:
            async with self.cliente.stream(
                "POST",
                "http://127.0.0.1:8001/transcribe",
                headers={"Authorization": "Bearer " + self.clave},
                json={"audio": audio},
            ) as respuesta:
                respuesta.raise_for_status()
                contenido = bytearray()
                async for fragmento in respuesta.aiter_bytes():
                    contenido.extend(fragmento)
                    if len(contenido) > 2000:
                        raise ValueError()
                texto = json.loads(contenido)["texto"]
                validar_consulta(texto)
                return texto
        except ErrorAplicacion:
            raise ErrorAplicacion(
                "No se reconoció una consulta. Intente nuevamente."
            ) from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ErrorAplicacion(
                "Voz no disponible. Escriba la consulta.", 503
            ) from None
        finally:
            self.ocupado = False
