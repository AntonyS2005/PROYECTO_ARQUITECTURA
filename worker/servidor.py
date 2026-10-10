import os

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "1048576")

import base64
import hashlib
import ipaddress
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import jwt
import numpy as np


DIRECTORIO_RAIZ = Path(__file__).resolve().parent
ID_MODELO = "sface-2021dec"
MAXIMO_CUERPO = 450_000


class ErrorFotografia(ValueError):
    pass


class MotorFacial:
    def __init__(self, directorio):
        manifiesto = json.loads((DIRECTORIO_RAIZ / "modelos.json").read_text())
        rutas = []
        for modelo in manifiesto["modelos"]:
            ruta = directorio / modelo["archivo"]
            if ruta.stat().st_size != modelo["bytes"] or hashlib.sha256(ruta.read_bytes()).hexdigest() != modelo["sha256"]:
                raise RuntimeError("Modelo ausente o con integridad no válida.")
            rutas.append(str(ruta))
        cv2.setNumThreads(2)
        self.detector = cv2.FaceDetectorYN.create(rutas[0], "", (640, 480), 0.8, 0.3, 5000)
        self.reconocedor = cv2.FaceRecognizerSF.create(rutas[1], "")
        self.lector_carne = cv2.QRCodeDetector()
        self.bloqueo = threading.Lock()

    def decodificar_fotografia(self, foto):
        if not isinstance(foto, str) or len(foto) > 400_000 or not foto.startswith("data:image/jpeg;base64,"):
            raise ValueError("Fotografía no válida.")
        contenido_original = base64.b64decode(foto[23:], validate=True)
        if not contenido_original.startswith(b"\xff\xd8\xff") or not contenido_original.endswith(b"\xff\xd9"):
            raise ValueError("Fotografía no válida.")
        imagen = cv2.imdecode(np.frombuffer(contenido_original, dtype=np.uint8), cv2.IMREAD_COLOR)
        if imagen is None or imagen.shape[0] < 80 or imagen.shape[1] < 80:
            raise ValueError("Fotografía demasiado pequeña o no válida.")
        return imagen

    def leer_carne(self, foto):
        imagen = self.decodificar_fotografia(foto)
        with self.bloqueo:
            identificador, _, _ = self.lector_carne.detectAndDecode(imagen)
            if not identificador:
                gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
                ampliada = cv2.resize(gris, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                identificador, _, _ = self.lector_carne.detectAndDecode(ampliada)
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", identificador, re.IGNORECASE):
            raise ValueError("QR del carné no válido.")
        return {"uuid": identificador.lower()}

    def extraer_vector(self, foto):
        imagen = self.decodificar_fotografia(foto)
        alto, ancho = imagen.shape[:2]
        if max(ancho, alto) > 640:
            escala = 640 / max(ancho, alto)
            imagen = cv2.resize(imagen, (round(ancho * escala), round(alto * escala)))
        
        with self.bloqueo:
            self.detector.setInputSize((imagen.shape[1], imagen.shape[0]))
            _, rostros = self.detector.detect(imagen)
            if rostros is None:
                reducida = cv2.resize(imagen, (max(40, imagen.shape[1] // 2), max(40, imagen.shape[0] // 2)))
                self.detector.setInputSize((reducida.shape[1], reducida.shape[0]))
                _, rostros = self.detector.detect(reducida)
                if rostros is not None:
                    for rostro in rostros:
                        rostro[:14].reshape(-1, 2)[:] *= (imagen.shape[1] / reducida.shape[1], imagen.shape[0] / reducida.shape[0])
            if rostros is None:
                raise ErrorFotografia("ROSTRO_NO_DETECTADO")
            if len(rostros) != 1:
                raise ErrorFotografia("VARIOS_ROSTROS")
            rostro_alineado = self.reconocedor.alignCrop(imagen, rostros[0])
            vector = self.reconocedor.feature(rostro_alineado).reshape(-1).astype(np.float64)
        norma = np.linalg.norm(vector)
        if vector.size != 128 or not np.all(np.isfinite(vector)) or norma <= 0:
            raise RuntimeError("Representación facial no válida.")
        return vector / norma

    def crear_miniatura(self, foto):
        imagen = self.decodificar_fotografia(foto)
        alto, ancho = imagen.shape[:2]
        for maximo, calidad in ((240, 40), (200, 30), (160, 20)):
            escala = min(1, maximo / max(ancho, alto))
            miniatura = cv2.resize(imagen, (round(ancho * escala), round(alto * escala)), interpolation=cv2.INTER_AREA)
            correcto, contenido = cv2.imencode(".webp", miniatura, [cv2.IMWRITE_WEBP_QUALITY, calidad])
            if correcto and contenido.nbytes <= 16_384:
                return base64.b64encode(contenido).decode("ascii")
        raise RuntimeError("No se pudo comprimir la captura.")

    def inferir(self, cuerpo):
        if not isinstance(cuerpo, dict) or cuerpo.get("operacion") not in ("registrar", "verificar", "leer-carne"):
            raise ValueError("Operación no válida.")
        if cuerpo["operacion"] == "leer-carne":
            return self.leer_carne(cuerpo.get("foto"))
        referencia = None
        umbral = cuerpo.get("umbral", 0.363)
        if cuerpo["operacion"] == "verificar":
            if type(umbral) not in (int, float) or not np.isfinite(umbral) or not -1 <= umbral <= 1:
                raise ValueError("Umbral no válido.")
            valores = cuerpo.get("vectorFacial")
            if not isinstance(valores, list) or len(valores) != 128 or any(type(valor) not in (int, float) for valor in valores):
                raise ValueError("Referencia no válida.")
            referencia = np.asarray(valores, dtype=np.float64)
            norma = np.linalg.norm(referencia)
            if not np.all(np.isfinite(referencia)) or not 0.99 < norma < 1.01:
                raise ValueError("Referencia no válida.")
            referencia = referencia / norma
        vector = self.extraer_vector(cuerpo.get("foto"))
        if referencia is None:
            return {"vectorFacial": vector.tolist()}
        similitud = float(np.clip(np.dot(vector, referencia), -1, 1))
        resultado = {"similitud": similitud}
        if similitud < umbral:
            resultado["fotoRechazo"] = self.crear_miniatura(cuerpo.get("foto"))
        return resultado


def crear_manejador(motor, id_nodo, clave_interna):
    class Manejador(BaseHTTPRequestHandler):
        def responder(self, estado_http, datos):
            contenido = json.dumps(datos, allow_nan=False).encode()
            self.send_response(estado_http)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(contenido)

        def esta_autorizado(self, alcance):
            direccion = ipaddress.ip_address(self.client_address[0])
            if not direccion.is_loopback and direccion not in ipaddress.ip_network("192.168.50.0/24"):
                self.responder(403, {"mensaje": "Red no permitida."})
                return False
            encabezado_autorizacion = self.headers.get("Authorization", "")
            try:
                if not encabezado_autorizacion.startswith("Bearer "):
                    raise ValueError("Token ausente.")
                datos_token = jwt.decode(encabezado_autorizacion[7:], clave_interna, algorithms=["HS256"], audience=id_nodo, issuer="edge-master",
                                    options={"require": ["exp", "iat", "aud", "iss", "scope"]})
                if datos_token["scope"] != alcance:
                    raise ValueError("Operación no autorizada.")
            except (jwt.PyJWTError, ValueError):
                self.responder(401, {"mensaje": "Solicitud no autorizada."})
                return False
            return True

        def do_GET(self):
            if self.path != "/health":
                return self.responder(404, {"mensaje": "Recurso no encontrado."})
            if self.esta_autorizado("health"):
                self.responder(200, {"nodo": id_nodo, "modelo": ID_MODELO})

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
                cuerpo = json.loads(self.rfile.read(longitud), parse_constant=lambda valor: None)
                inicio = time.perf_counter()
                resultado = motor.inferir(cuerpo)
                self.responder(200, {"nodo": id_nodo, "modelo": ID_MODELO,
                                 "duracionMs": round((time.perf_counter() - inicio) * 1000, 2), **resultado})
            except ErrorFotografia as error:
                self.responder(422, {"codigo": str(error), "mensaje": "No se pudo detectar un rostro individual."})
            except (ValueError, cv2.error):
                self.responder(422, {"codigo": "FOTO_NO_VALIDA", "mensaje": "No se pudo leer la fotografía."})
            except Exception as error:
                print(f"Fallo de worker: {type(error).__name__}", flush=True)
                self.responder(500, {"mensaje": "No se pudo procesar la solicitud."})

        def log_message(self, formato, *argumentos):
            
            pass

    return Manejador


def principal():
    id_nodo = os.environ.get("ID_NODO", "")
    clave_interna = os.environ.get("CLAVE_NODOS", "")
    direccion_escucha = os.environ.get("HOST", "127.0.0.1")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", id_nodo) or len(clave_interna) < 32:
        raise RuntimeError("Defina ID_NODO y CLAVE_NODOS (al menos 32 caracteres).")
    if direccion_escucha not in ("127.0.0.1", "192.168.50.11", "192.168.50.12"):
        raise RuntimeError("HOST no corresponde a un worker del montaje.")
    motor = MotorFacial(Path(os.environ.get("DIRECTORIO_MODELOS", DIRECTORIO_RAIZ / "modelos")))
    servidor = ThreadingHTTPServer((direccion_escucha, int(os.environ.get("PORT", "8000"))), crear_manejador(motor, id_nodo, clave_interna))
    servidor.daemon_threads = True
    print(f"Worker {id_nodo} disponible en {direccion_escucha}:{servidor.server_port}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    principal()
