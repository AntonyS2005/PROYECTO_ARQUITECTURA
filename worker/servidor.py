from http.server import ThreadingHTTPServer

from .api.manejador import crear_manejador
from .infraestructura.imagenes import crear_miniatura, decodificar_fotografia
from .infraestructura.vision import MotorVision
from .nucleo.configuracion import Configuracion
from .servicios.inferencia import ServicioInferencia


def principal():
    configuracion = Configuracion.cargar()
    motor = MotorVision(configuracion.directorio_modelos)
    servicio = ServicioInferencia(motor, decodificar_fotografia, crear_miniatura)
    manejador = crear_manejador(
        servicio, configuracion.id_nodo, configuracion.clave_interna
    )
    servidor = ThreadingHTTPServer(
        (configuracion.direccion, configuracion.puerto), manejador
    )
    servidor.daemon_threads = True
    print(
        f"Worker {configuracion.id_nodo} disponible en {configuracion.direccion}:{servidor.server_port}",
        flush=True,
    )
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    principal()
