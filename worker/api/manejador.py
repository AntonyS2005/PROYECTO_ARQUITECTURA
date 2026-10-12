import json
import time
from http.server import BaseHTTPRequestHandler

import cv2

from ..nucleo.configuracion import ID_MODELO, MAXIMO_CUERPO
from ..nucleo.errores import ErrorFotografia
from .seguridad import ErrorAutorizacion, validar_autorizacion


def crear_manejador(servicio, id_nodo, clave_interna):
    class Manejador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def responder(self, estado_http, datos):
            contenido = json.dumps(datos, allow_nan=False).encode()
            self.send_response(estado_http)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Cache-Control", "no-store")
            if estado_http >= 400:
                self.close_connection = True
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(contenido)

        def esta_autorizado(self, alcance):
            try:
                validar_autorizacion(
                    self.client_address[0],
                    self.headers.get("Authorization", ""),
                    alcance,
                    id_nodo,
                    clave_interna,
                )
            except ErrorAutorizacion as error:
                self.responder(error.estado, {"mensaje": str(error)})
                return False
            return True

        def do_GET(self):
            if self.path != "/health":
                return self.responder(404, {"mensaje": "Recurso no encontrado."})
            if self.esta_autorizado("health"):
                self.responder(
                    200, {"nodo": id_nodo, "modelo": ID_MODELO, "modo": servicio.modo}
                )

        def do_POST(self):
            if self.path != "/infer":
                return self.responder(404, {"mensaje": "Recurso no encontrado."})
            if not self.esta_autorizado("inference"):
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.responder(415, {"mensaje": "Formato no válido."})
            try:
                self.connection.settimeout(10)
                longitud = int(self.headers.get("Content-Length", "0"))
                if not 0 < longitud <= MAXIMO_CUERPO:
                    return self.responder(413, {"mensaje": "Tamaño no permitido."})
                cuerpo = json.loads(
                    self.rfile.read(longitud), parse_constant=lambda valor: None
                )
                inicio = time.perf_counter()
                resultado = servicio.inferir(cuerpo)
                self.responder(
                    200,
                    {
                        "nodo": id_nodo,
                        "modelo": ID_MODELO,
                        "duracionMs": round((time.perf_counter() - inicio) * 1000, 2),
                        **resultado,
                    },
                )
            except ErrorFotografia as error:
                self.responder(
                    422,
                    {
                        "codigo": str(error),
                        "mensaje": "No se pudo detectar un rostro individual.",
                    },
                )
            except (ValueError, cv2.error):
                self.responder(
                    422,
                    {
                        "codigo": "FOTO_NO_VALIDA",
                        "mensaje": "No se pudo leer la fotografía.",
                    },
                )
            except Exception as error:
                print(f"Fallo de worker: {type(error).__name__}", flush=True)
                self.responder(500, {"mensaje": "No se pudo procesar la solicitud."})

        def log_message(self, formato, *argumentos):
            pass

    return Manejador
