import csv
import io
import json

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ..dependencias import Administrador, BaseDatos, Cuenta, obtener_periodo, validar_id
from ..errores import ErrorAplicacion
from ..gestor_nodos import nodos_no_disponibles
from ..servicio_accesos import ServicioAccesos
from ..validaciones import CapturaAcceso

rutas = APIRouter(prefix="/api")


@rutas.post("/accesos", status_code=201)
async def registrar(
    datos: CapturaAcceso, solicitud: Request, cuenta: Cuenta, base_datos: BaseDatos
):
    nodos = solicitud.app.state.nodos
    if not nodos:
        raise nodos_no_disponibles()
    lectura = await nodos.ejecutar_inferencia("leer-carne", {"foto": datos.fotoCarne})
    persona = base_datos.execute(
        "SELECT * FROM personas WHERE uuid=? AND activo=1", (lectura["uuid"].lower(),)
    ).fetchone()
    if not persona:
        raise ErrorAplicacion(
            "Carné no disponible.",
            errores={"fotoCarne": "El carné no está registrado o está desactivado."},
        )
    umbral = solicitud.app.state.configuracion.umbral_facial
    resultado = await nodos.ejecutar_inferencia(
        "verificar",
        {
            "foto": datos.foto,
            "umbral": umbral,
            "vectorFacial": json.loads(persona["vector_facial"]),
        },
    )
    if resultado["modelo"] != persona["modelo"]:
        raise nodos_no_disponibles()
    evento = ServicioAccesos(base_datos).registrar_acceso(
        persona, {**resultado, "umbral": umbral}, cuenta["id"]
    )
    mensaje = (
        "Verificación no aprobada."
        if evento["estado"] == "RECHAZADO"
        else ("Entrada" if evento["tipo"] == "ENTRADA" else "Salida") + " registrada."
    )
    return {"evento": evento, "mensaje": mensaje}


@rutas.get("/eventos")
async def historial(solicitud: Request, cuenta: Cuenta, base_datos: BaseDatos):
    periodo = obtener_periodo(solicitud) if cuenta["rol"] == "ADMINISTRADOR" else None
    return ServicioAccesos(base_datos).consultar_historial(cuenta, periodo)


@rutas.get("/eventos/{id}/foto")
async def consultar_foto(id: str, cuenta: Administrador, base_datos: BaseDatos):
    captura = base_datos.execute(
        "SELECT f.foto FROM fotografias_rechazos f JOIN eventos e ON e.id=f.evento_id WHERE e.id=? AND e.estado='RECHAZADO'",
        (validar_id(id),),
    ).fetchone()
    if not captura:
        raise ErrorAplicacion("Fotografía no disponible.", 404)
    return Response(captura["foto"], media_type="image/webp")


@rutas.get("/metricas")
async def metricas(solicitud: Request, cuenta: Administrador, base_datos: BaseDatos):
    return ServicioAccesos(base_datos).consultar_metricas(obtener_periodo(solicitud))


@rutas.get("/exportar")
async def exportar(solicitud: Request, cuenta: Administrador, base_datos: BaseDatos):
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
    registros = ServicioAccesos(base_datos).consultar_historial(
        cuenta, obtener_periodo(solicitud)
    )
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
