import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ...esquemas.entradas import CapturaAcceso
from ..dependencias import (
    Accesos,
    Administrador,
    Cuenta,
    CuentaInferencia,
    obtener_periodo,
    validar_id,
)

rutas = APIRouter(prefix="/api")


@rutas.post("/accesos", status_code=201)
async def registrar(datos: CapturaAcceso, cuenta: CuentaInferencia, accesos: Accesos):
    evento = await accesos.validar_captura(datos, cuenta["id"])
    mensaje = (
        "Verificación no aprobada."
        if evento["estado"] == "RECHAZADO"
        else ("Entrada" if evento["tipo"] == "ENTRADA" else "Salida") + " registrada."
    )
    return {"evento": evento, "mensaje": mensaje}


@rutas.get("/eventos")
async def historial(solicitud: Request, cuenta: Cuenta, accesos: Accesos):
    periodo = obtener_periodo(solicitud) if cuenta["rol"] == "ADMINISTRADOR" else None
    return accesos.consultar_historial(cuenta, periodo)


@rutas.get("/eventos/{id}/foto")
async def consultar_foto(id: str, cuenta: Administrador, accesos: Accesos):
    return Response(accesos.consultar_foto(validar_id(id)), media_type="image/webp")


@rutas.get("/metricas")
async def metricas(solicitud: Request, cuenta: Administrador, accesos: Accesos):
    return accesos.consultar_metricas(obtener_periodo(solicitud))


@rutas.get("/exportar")
async def exportar(solicitud: Request, cuenta: Administrador, accesos: Accesos):
    columnas = [
        "uuid",
        "nombres",
        "apellidos",
        "tipo",
        "estado",
        "similitud",
        "umbral",
        "modelo",
        "fecha_hora",
        "nodo",
        "usuario",
    ]
    registros = accesos.consultar_historial(cuenta, obtener_periodo(solicitud))
    contenido = io.StringIO()
    escritor = csv.writer(contenido, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    escritor.writerow(columnas)
    for registro in registros:
        fila = []
        for columna in columnas:
            valor = "" if registro[columna] is None else str(registro[columna])
            fila.append(
                "'" + valor if valor.startswith(("=", "+", "@", "-")) else valor
            )
        escritor.writerow(fila)
    return Response(
        "\ufeff" + contenido.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="reporte-accesos.csv"'},
    )
