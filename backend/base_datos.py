import sqlite3
from pathlib import Path


def conectar(ruta):
    conexion = sqlite3.connect(str(ruta), isolation_level=None, timeout=5)
    conexion.row_factory = lambda cursor, fila: dict(
        zip([columna[0] for columna in cursor.description], fila)
    )
    conexion.execute("PRAGMA foreign_keys=ON")
    return conexion


def abrir_base_datos(ruta):
    conexion = conectar(ruta)
    try:
        columnas = conexion.execute("PRAGMA table_info(personas)").fetchall()
        columnas += conexion.execute("PRAGMA table_info(persons)").fetchall()
        if any(columna["name"] == "cui" for columna in columnas):
            raise ValueError(
                "La base existente corresponde a la versión DPI. Consérvela como respaldo y use una base nueva para carnés."
            )
        conexion.executescript(
            Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8")
        )
        return conexion
    except Exception:
        conexion.close()
        raise
