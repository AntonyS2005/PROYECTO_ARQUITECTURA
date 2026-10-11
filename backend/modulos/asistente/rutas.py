import base64
import binascii
import json
import re
import unicodedata
from datetime import datetime, time, timedelta

import httpx
from fastapi import APIRouter, Request

from ...dependencias import BaseDatos, Cuenta
from ...errores import ErrorAplicacion
from ...servicio_accesos import ServicioAccesos, fecha_iso

INTENCIONES = {
    "ayuda": {"tipo": "ayuda"},
    "abrir registro": {"tipo": "navegar", "vista": "operacion"},
    "abrir carnes": {"tipo": "navegar", "vista": "carnes", "administrador": True},
    "abrir reportes": {"tipo": "navegar", "vista": "reportes", "administrador": True},
    "estado de los nodos": {"tipo": "navegar", "vista": "nodo", "administrador": True},
    "capturar foto": {"tipo": "capturar"},
    "cuantas personas hay dentro": {"tipo": "aforo", "administrador": True},
    "mostrar las entradas de hoy": {"tipo": "entradas", "administrador": True},
    "cuantas entradas hubo hoy": {"tipo": "entradas", "administrador": True},
}


def validar_consulta(texto):
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorAplicacion(
            "Revise la consulta.", errores={"texto": "Ingrese una consulta."}
        )
    if len(texto) > 200:
        raise ErrorAplicacion(
            "Revise la consulta.", errores={"texto": "Máximo 200 caracteres."}
        )


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


def crear_rutas(voz_habilitada):
    rutas = APIRouter(prefix="/api/asistente")

    @rutas.post("/consulta")
    async def consultar(
        datos: dict, solicitud: Request, cuenta: Cuenta, base_datos: BaseDatos
    ):
        texto = datos.get("texto")
        validar_consulta(texto)
        normalizado = "".join(
            letra
            for letra in unicodedata.normalize("NFD", texto)
            if unicodedata.category(letra)[0] != "M"
        )
        normalizado = re.sub(r"[¿?¡!.,]", "", normalizado.lower())
        intencion = INTENCIONES.get(" ".join(normalizado.split()))
        if not intencion:
            raise ErrorAplicacion(
                "Comando no reconocido.",
                errores={"texto": "Consulte los comandos disponibles."},
            )
        if intencion.get("administrador") and cuenta["rol"] != "ADMINISTRADOR":
            raise ErrorAplicacion("Acceso no autorizado.", 403)
        tipo = intencion["tipo"]
        if tipo == "ayuda":
            return {
                "mensaje": "Comandos: abrir registro, capturar foto. Administración: abrir carnés, abrir reportes, estado de los nodos, cuántas personas hay dentro, mostrar las entradas de hoy."
            }
        if tipo == "navegar":
            return {
                "mensaje": "Vista seleccionada.",
                "accion": {"tipo": tipo, "vista": intencion["vista"]},
            }
        if tipo == "capturar":
            return {
                "mensaje": "Seleccione Registro de acceso y active la cámara antes de capturar.",
                "accion": {"tipo": tipo},
            }
        zona = solicitud.app.state.zona_horaria
        hoy = datetime.now(zona).date()
        periodo = {
            "inicio": fecha_iso(datetime.combine(hoy, time.min, zona)),
            "fin": fecha_iso(datetime.combine(hoy + timedelta(days=1), time.min, zona)),
        }
        metricas = ServicioAccesos(base_datos).consultar_metricas(periodo)
        return {
            "mensaje": f"Personas dentro según los registros: {metricas['aforo']}."
            if tipo == "aforo"
            else f"Entradas registradas hoy: {metricas['entradas']}."
        }

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
