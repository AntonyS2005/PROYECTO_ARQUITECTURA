import os
import re
from dataclasses import dataclass
from pathlib import Path

DIRECTORIO_RAIZ = Path(__file__).resolve().parents[1]
ID_MODELO = "sface-2021dec"
MAXIMO_CUERPO = 450_000


@dataclass(frozen=True)
class Configuracion:
    id_nodo: str
    clave_interna: str
    direccion: str
    puerto: int
    directorio_modelos: Path

    @classmethod
    def cargar(cls):
        id_nodo = os.getenv("ID_NODO", "")
        clave_interna = os.getenv("CLAVE_NODOS", "")
        direccion = os.getenv("HOST", "127.0.0.1")
        puerto = int(os.getenv("PORT", "8000"))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", id_nodo) or len(clave_interna) < 32:
            raise RuntimeError("Defina ID_NODO y CLAVE_NODOS (al menos 32 caracteres).")
        if direccion not in ("127.0.0.1", "192.168.50.11", "192.168.50.12"):
            raise RuntimeError("HOST no corresponde a un worker del montaje.")
        if not 1 <= puerto <= 65535:
            raise RuntimeError("PORT debe estar entre 1 y 65535.")
        return cls(
            id_nodo,
            clave_interna,
            direccion,
            puerto,
            Path(os.getenv("DIRECTORIO_MODELOS", DIRECTORIO_RAIZ / "modelos")),
        )
