import math
import time


class LimitadorSolicitudes:
    def __init__(self, maximo_registros=2048):
        self.registros = {}
        self.maximo_registros = maximo_registros
        self.proxima_limpieza = 0

    def admitir(self, clave, limite, segundos=60):
        ahora = time.monotonic()
        if ahora >= self.proxima_limpieza:
            self.registros = {
                clave: valor
                for clave, valor in self.registros.items()
                if valor[1] > ahora
            }
            self.proxima_limpieza = ahora + 30
        cantidad, vencimiento = self.registros.get(clave, (0, ahora + segundos))
        if vencimiento <= ahora:
            cantidad, vencimiento = 0, ahora + segundos
        if cantidad >= limite:
            return max(1, math.ceil(vencimiento - ahora))
        if clave not in self.registros and len(self.registros) >= self.maximo_registros:
            return 30
        self.registros[clave] = cantidad + 1, vencimiento
        return 0
