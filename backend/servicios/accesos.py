import json
import math
from datetime import datetime, timezone

from ..nucleo.errores import ErrorAplicacion, nodos_no_disponibles
from ..nucleo.fechas import fecha_iso
from ..nucleo.fotografias import MAXIMO_FOTOGRAFIAS, decodificar_foto_rechazo


class ServicioAccesos:
    def __init__(self, eventos, personas, nodos=None, umbral=0.363):
        self.eventos = eventos
        self.personas = personas
        self.nodos = nodos
        self.umbral = umbral

    async def validar_captura(self, datos, usuario_id):
        if not self.nodos:
            raise nodos_no_disponibles()
        lectura = await self.nodos.ejecutar_inferencia(
            "leer-carne", {"foto": datos.fotoCarne}
        )
        persona = self.personas.obtener_por_uuid(lectura["uuid"].lower())
        if not persona or not persona["activo"]:
            raise ErrorAplicacion(
                "Carné no disponible.",
                errores={
                    "fotoCarne": "El carné no está registrado o está desactivado."
                },
            )
        resultado = await self.nodos.ejecutar_inferencia(
            "verificar",
            {
                "foto": datos.foto,
                "umbral": self.umbral,
                "vectorFacial": json.loads(persona["vector_facial"]),
            },
        )
        if resultado["modelo"] != persona["modelo"]:
            raise nodos_no_disponibles()
        return self.registrar_acceso(
            persona, {**resultado, "umbral": self.umbral}, usuario_id
        )

    def registrar_acceso(self, persona, verificacion, usuario_id):
        fecha = fecha_iso()
        autorizado = verificacion["similitud"] >= verificacion["umbral"]
        foto = (
            None
            if autorizado
            else decodificar_foto_rechazo(verificacion.get("fotoRechazo"))
        )
        with self.eventos.transaccion():
            if not self.eventos.persona_activa(persona["id"]):
                raise ErrorAplicacion("Carné no disponible.", 409)
            anterior = self.eventos.ultimo_autorizado(persona["id"])
            tipo = (
                ("SALIDA" if anterior and anterior["tipo"] == "ENTRADA" else "ENTRADA")
                if autorizado
                else None
            )
            duracion = None
            if tipo == "SALIDA":
                duracion = max(
                    0,
                    (
                        datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                        - datetime.fromisoformat(
                            anterior["fecha_hora"].replace("Z", "+00:00")
                        )
                    ).total_seconds(),
                )
            identificador = self.eventos.insertar(
                {
                    "persona_id": persona["id"],
                    "usuario_id": usuario_id,
                    "uuid": persona["uuid"],
                    "nombres": persona["nombres"],
                    "apellidos": persona["apellidos"],
                    "tipo": tipo,
                    "estado": "AUTORIZADO" if autorizado else "RECHAZADO",
                    "similitud": verificacion["similitud"],
                    "umbral": verificacion["umbral"],
                    "nodo": verificacion["nodo"],
                    "modelo": verificacion["modelo"],
                    "fecha_hora": fecha,
                    "duracion_segundos": duracion,
                }
            )
            if foto:
                self.eventos.guardar_foto(identificador, foto, MAXIMO_FOTOGRAFIAS)
        return self.eventos.obtener(identificador)

    def consultar_historial(self, cuenta, periodo=None):
        if cuenta["rol"] == "OPERADOR":
            inicio = fecha_iso(
                datetime.fromtimestamp(cuenta["inicioSesion"], timezone.utc)
            )
            return self.eventos.historial_operador(cuenta["id"], inicio)
        return self.eventos.historial_periodo(periodo)

    def consultar_foto(self, identificador):
        foto = self.eventos.obtener_foto(identificador)
        if foto is None:
            raise ErrorAplicacion("Fotografía no disponible.", 404)
        return foto

    def consultar_metricas(self, periodo):
        conteos, horas, recurrencia, aforo = self.eventos.consultar_metricas(periodo)
        conteos["promedioMinutos"] = math.floor(conteos["promedioMinutos"] + 0.5)
        totales = {fila["hora"]: fila["total"] for fila in horas}
        return {
            **conteos,
            "aforo": aforo,
            "recurrencia": recurrencia,
            "horas": [
                {"hora": hora, "total": totales.get(hora, 0)} for hora in range(24)
            ],
        }
