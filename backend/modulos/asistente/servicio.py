import re
import unicodedata
from datetime import datetime, time, timedelta

from ...nucleo.errores import ErrorAplicacion
from ...nucleo.fechas import fecha_iso

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


class ServicioAsistente:
    def __init__(self, accesos, zona_horaria):
        self.accesos = accesos
        self.zona_horaria = zona_horaria

    def consultar(self, texto, cuenta):
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
        zona = self.zona_horaria
        hoy = datetime.now(zona).date()
        periodo = {
            "inicio": fecha_iso(datetime.combine(hoy, time.min, zona)),
            "fin": fecha_iso(datetime.combine(hoy + timedelta(days=1), time.min, zona)),
        }
        metricas = self.accesos.consultar_metricas(periodo)
        return {
            "mensaje": f"Personas dentro según los registros: {metricas['aforo']}."
            if tipo == "aforo"
            else f"Entradas registradas hoy: {metricas['entradas']}."
        }
