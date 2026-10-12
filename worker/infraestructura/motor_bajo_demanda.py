import multiprocessing
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from .vision import MotorVision


motor = None


def cargar_motor(directorio):
    global motor
    motor = MotorVision(directorio)


def ejecutar_operacion(operacion, imagen):
    return getattr(motor, operacion)(imagen)


class MotorBajoDemanda:
    def __init__(self, directorio, segundos_reposo):
        self.directorio = directorio
        self.segundos_reposo = segundos_reposo
        self.proceso = None
        self.ultimo_uso = time.monotonic()
        self.bloqueo = threading.Lock()
        self.cerrado = threading.Event()
        self.supervisor = threading.Thread(target=self.supervisar, daemon=True)
        self.supervisor.start()

    @property
    def en_reposo(self):
        with self.bloqueo:
            return self.proceso is None

    def ejecutar(self, operacion, imagen):
        with self.bloqueo:
            if self.cerrado.is_set():
                raise RuntimeError("El servicio de inferencia está cerrado.")
            if self.proceso is None:
                self.proceso = ProcessPoolExecutor(
                    max_workers=1,
                    mp_context=multiprocessing.get_context("spawn"),
                    initializer=cargar_motor,
                    initargs=(self.directorio,),
                )
            try:
                return self.proceso.submit(ejecutar_operacion, operacion, imagen).result()
            except BrokenProcessPool:
                self.liberar()
                raise
            finally:
                self.ultimo_uso = time.monotonic()

    def leer_carne(self, imagen):
        return self.ejecutar("leer_carne", imagen)

    def extraer_vector(self, imagen):
        return self.ejecutar("extraer_vector", imagen)

    def liberar(self):
        if self.proceso is not None:
            self.proceso.shutdown(wait=True, cancel_futures=True)
            self.proceso = None

    def supervisar(self):
        while not self.cerrado.wait(min(30, self.segundos_reposo)):
            with self.bloqueo:
                if time.monotonic() - self.ultimo_uso >= self.segundos_reposo:
                    self.liberar()

    def cerrar(self):
        self.cerrado.set()
        self.supervisor.join()
        with self.bloqueo:
            self.liberar()
