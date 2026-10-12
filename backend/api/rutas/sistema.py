import os
import time

import psutil
from fastapi import APIRouter, Request

from ..dependencias import Administrador

rutas = APIRouter(prefix="/api")


@rutas.get("/nodo")
async def consultar(solicitud: Request, cuenta: Administrador):
    nodos = solicitud.app.state.nodos
    return {
        "nombre": os.uname().nodename
        if hasattr(os, "uname")
        else os.getenv("COMPUTERNAME", "Local"),
        "tiempoActivoSegundos": int(time.monotonic() - solicitud.app.state.inicio),
        "memoriaMb": round(psutil.Process().memory_info().rss / 1024 / 1024),
        "modo": "Clúster local · Carnés",
        "baseDatos": "SQLite",
        "nodos": await nodos.consultar_estado() if nodos else [],
    }
