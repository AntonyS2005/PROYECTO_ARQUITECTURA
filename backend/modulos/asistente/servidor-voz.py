import base64
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel

MAXIMO_AUDIO = 256000
MAXIMO_CUERPO = 350000


def crear_manejador(modelo, clave_interna):
    class Manejador(BaseHTTPRequestHandler):
        def responder(self, estado_http, cuerpo):
            contenido_original = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
            self.send_response(estado_http)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido_original)))
            self.end_headers()
            self.wfile.write(contenido_original)

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != "/transcribe":
                return self.responder(404, {"mensaje": "Recurso no encontrado."})
            if not hmac.compare_digest(
                self.headers.get("Authorization", "").encode(),
                ("Bearer " + clave_interna).encode(),
            ):
                return self.responder(401, {"mensaje": "Acceso no autorizado."})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.responder(415, {"mensaje": "Formato no válido."})
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
                if not 0 < longitud <= MAXIMO_CUERPO:
                    return self.responder(413, {"mensaje": "Audio demasiado largo."})
                cuerpo = json.loads(self.rfile.read(longitud))
                if not isinstance(cuerpo, dict) or not isinstance(
                    cuerpo.get("audio"), str
                ):
                    raise ValueError("Audio ausente")
                audio = base64.b64decode(cuerpo["audio"], validate=True)
                if not 3200 <= len(audio) <= MAXIMO_AUDIO or len(audio) % 2:
                    raise ValueError("Longitud no válida")
            except (ValueError, TypeError):
                return self.responder(422, {"mensaje": "Audio no válido."})
            try:
                reconocedor = KaldiRecognizer(modelo, 16000)
                partes = []
                for desplazamiento in range(0, len(audio), 4000):
                    if reconocedor.AcceptWaveform(
                        audio[desplazamiento : desplazamiento + 4000]
                    ):
                        partes.append(json.loads(reconocedor.Result()).get("text", ""))
                partes.append(json.loads(reconocedor.FinalResult()).get("text", ""))
                texto = " ".join(parte for parte in partes if parte).strip()
                if len(texto) > 200:
                    return self.responder(
                        422, {"mensaje": "La consulta supera 200 caracteres."}
                    )
                self.responder(200, {"texto": texto})
            except Exception:
                self.responder(503, {"mensaje": "Voz no disponible."})

        def log_message(self, formato, *argumentos):
            pass

    return Manejador


def principal():
    clave_interna = os.environ.get("CLAVE_VOZ", "")
    if len(clave_interna) < 32:
        raise RuntimeError("Defina CLAVE_VOZ con al menos 32 caracteres.")
    directorio = Path(os.environ.get("DIRECTORIO_MODELO_VOZ", ""))
    if not (directorio / "am" / "final.mdl").is_file():
        raise RuntimeError("Instale el modelo local de voz antes de iniciar.")
    SetLogLevel(-1)
    modelo = Model(str(directorio))
    servidor = HTTPServer(("127.0.0.1", 8001), crear_manejador(modelo, clave_interna))
    print("Servicio local de voz disponible.", flush=True)
    try:
        servidor.serve_forever()
    finally:
        servidor.server_close()


if __name__ == "__main__":
    principal()
