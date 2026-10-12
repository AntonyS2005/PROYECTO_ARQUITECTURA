import threading
from http.server import ThreadingHTTPServer


class ServidorInferencia(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, direccion, manejador):
        super().__init__(direccion, manejador)
        self.conexiones = threading.BoundedSemaphore(8)

    def process_request(self, solicitud, direccion):
        if not self.conexiones.acquire(blocking=False):
            self.shutdown_request(solicitud)
            return
        try:
            super().process_request(solicitud, direccion)
        except Exception:
            self.conexiones.release()
            raise

    def process_request_thread(self, solicitud, direccion):
        try:
            super().process_request_thread(solicitud, direccion)
        finally:
            self.conexiones.release()
