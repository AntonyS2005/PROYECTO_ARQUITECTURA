from .api.manejador import crear_manejador
from .infraestructura.imagenes import crear_miniatura, decodificar_fotografia
from .infraestructura.motor_bajo_demanda import MotorBajoDemanda
from .infraestructura.servidor_http import ServidorInferencia
from .nucleo.configuracion import Configuracion
from .servicios.inferencia import ServicioInferencia


def principal():
    configuracion = Configuracion.cargar()
    motor = MotorBajoDemanda(
        configuracion.directorio_modelos, configuracion.segundos_reposo
    )
    servicio = ServicioInferencia(motor, decodificar_fotografia, crear_miniatura)
    manejador = crear_manejador(
        servicio, configuracion.id_nodo, configuracion.clave_interna
    )
    servidor = ServidorInferencia(
        (configuracion.direccion, configuracion.puerto), manejador
    )
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
        motor.cerrar()


if __name__ == "__main__":
    principal()
