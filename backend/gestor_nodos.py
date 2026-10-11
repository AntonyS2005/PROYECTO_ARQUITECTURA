import asyncio
import json
import math
import re
import time
from urllib.parse import urlparse

import httpx
import jwt

from .errores import ErrorAplicacion
from .fotografias_rechazos import decodificar_foto_rechazo
from .validaciones import PATRON_UUID


def nodos_no_disponibles():
    return ErrorAplicacion(
        "No hay nodos de verificación disponibles. Intente nuevamente.", 503
    )


def es_vector_facial_valido(valor):
    return (
        isinstance(valor, list)
        and len(valor) == 128
        and all(
            type(numero) in (int, float)
            and math.isfinite(numero)
            and abs(numero) <= 1.001
            for numero in valor
        )
        and 0.99 < math.sqrt(sum(numero**2 for numero in valor)) < 1.01
    )


class GestorNodos:
    def __init__(self, nodos, clave_interna, espera_ms=5000):
        if not isinstance(nodos, list) or not 1 <= len(nodos) <= 8:
            raise ValueError(
                "Configure entre uno y ocho workers con identificadores únicos."
            )
        if (
            not isinstance(clave_interna, str)
            or len(clave_interna) < 32
            or not 100 <= espera_ms <= 30000
        ):
            raise ValueError("Clave de workers o tiempo de espera no válido.")
        self.nodos = []
        for nodo in nodos:
            url = urlparse(nodo["url"])
            direccion = url.hostname or ""
            if (
                not re.fullmatch(r"[a-zA-Z0-9_-]{1,50}", nodo["id"])
                or url.scheme != "http"
                or url.username
                or url.password
                or url.query
                or url.fragment
                or url.path not in ("", "/")
                or not re.fullmatch(r"127\.0\.0\.1|192\.168\.50\.\d{1,3}", direccion)
                or any(int(parte) > 255 for parte in direccion.split("."))
            ):
                raise ValueError("Worker fuera de la red local permitida.")
            self.nodos.append({"id": nodo["id"], "url": nodo["url"].rstrip("/")})
        if len({nodo["id"] for nodo in self.nodos}) != len(self.nodos):
            raise ValueError("Los identificadores de los workers deben ser únicos.")
        self.clave_interna = clave_interna
        self.espera = espera_ms / 1000
        self.indice_actual = 0
        self.cliente = httpx.AsyncClient(
            timeout=self.espera, trust_env=False, follow_redirects=False
        )

    async def cerrar(self):
        await self.cliente.aclose()

    async def solicitar(self, nodo, ruta, contenido=None):
        async def enviar():
            ahora = int(time.time())
            token = jwt.encode(
                {
                    "scope": "health" if ruta == "/health" else "inference",
                    "iss": "edge-master",
                    "aud": nodo["id"],
                    "iat": ahora,
                    "exp": ahora + 30,
                },
                self.clave_interna,
                algorithm="HS256",
            )
            async with self.cliente.stream(
                "POST" if contenido else "GET",
                nodo["url"] + ruta,
                headers={"Authorization": "Bearer " + token},
                json=contenido,
            ) as respuesta:
                cuerpo = bytearray()
                async for fragmento in respuesta.aiter_bytes():
                    cuerpo.extend(fragmento)
                    if len(cuerpo) > 24000:
                        raise ValueError("Respuesta de worker demasiado grande.")
                datos = json.loads(cuerpo)
                if not isinstance(datos, dict):
                    raise ValueError("Respuesta de worker no válida.")
                if respuesta.status_code == 422:
                    if contenido and contenido["operacion"] == "leer-carne":
                        raise ErrorAplicacion(
                            "No se pudo leer el carné.",
                            codigo="QR_NO_LEIBLE",
                            errores={
                                "fotoCarne": "Coloque el QR del carné dentro del área indicada."
                            },
                        )
                    mensaje = {
                        "ROSTRO_NO_DETECTADO": "No se detectó el rostro. Use una fotografía de frente y con buena iluminación.",
                        "VARIOS_ROSTROS": "Se detectó más de un rostro. Use una fotografía individual.",
                        "FOTO_NO_VALIDA": "No se pudo leer la fotografía. Seleccione otro archivo.",
                    }.get(
                        datos.get("codigo"),
                        "No se pudo procesar el rostro. Use una fotografía clara con una sola persona.",
                    )
                    raise ErrorAplicacion(
                        mensaje, errores={"foto": mensaje}, codigo=datos.get("codigo")
                    )
                if not respuesta.is_success or datos.get("nodo") != nodo["id"]:
                    raise ValueError("Worker no disponible.")
                return datos

        return await asyncio.wait_for(enviar(), timeout=self.espera)

    async def ejecutar_inferencia(self, operacion, contenido):
        if operacion not in ("registrar", "verificar", "leer-carne"):
            raise ValueError("Operación no válida.")
        inicio = self.indice_actual
        self.indice_actual = (inicio + 1) % len(self.nodos)
        for desplazamiento in range(len(self.nodos)):
            nodo = self.nodos[(inicio + desplazamiento) % len(self.nodos)]
            try:
                datos = await self.solicitar(
                    nodo, "/infer", {**contenido, "operacion": operacion}
                )
                correcto = datos.get("modelo") == "sface-2021dec"
                if operacion == "leer-carne":
                    correcto = (
                        correcto
                        and isinstance(datos.get("uuid"), str)
                        and PATRON_UUID.fullmatch(datos["uuid"])
                    )
                elif operacion == "registrar":
                    correcto = correcto and es_vector_facial_valido(
                        datos.get("vectorFacial")
                    )
                else:
                    similitud = datos.get("similitud")
                    correcto = (
                        correcto
                        and type(similitud) in (int, float)
                        and math.isfinite(similitud)
                        and -1 <= similitud <= 1
                    )
                    if correcto and similitud < contenido.get("umbral", 0.363):
                        correcto = bool(
                            decodificar_foto_rechazo(datos.get("fotoRechazo"))
                        )
                if not correcto:
                    raise ValueError("Resultado de inferencia no válido.")
                return datos
            except ErrorAplicacion as error:
                if error.estado == 422:
                    raise
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                asyncio.TimeoutError,
            ):
                pass
        raise nodos_no_disponibles()

    async def consultar_estado(self):
        async def consultar(nodo):
            inicio = time.monotonic()
            try:
                datos = await self.solicitar(nodo, "/health")
                if datos.get("modelo") != "sface-2021dec":
                    raise ValueError()
                return {
                    "id": nodo["id"],
                    "status": "En línea",
                    "latenciaMs": round((time.monotonic() - inicio) * 1000),
                    "modelo": datos["modelo"],
                }
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                ErrorAplicacion,
                asyncio.TimeoutError,
            ):
                return {
                    "id": nodo["id"],
                    "status": "Sin respuesta",
                    "latenciaMs": None,
                    "modelo": None,
                }

        return await asyncio.gather(*(consultar(nodo) for nodo in self.nodos))
