import math
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class Configuracion:
    clave_sesion: str
    ruta_base: Path = RAIZ / "data/access.sqlite"
    horas_sesion: float = 8
    minutos_inactividad: float = 15
    cookie_segura: bool = False
    umbral_facial: float = 0.363
    asistente_habilitado: bool = False
    voz_habilitada: bool = False
    clave_voz: str = ""

    def __post_init__(self):
        if len(self.clave_sesion) < 32:
            raise ValueError("CLAVE_SESION requiere al menos 32 caracteres.")
        if any(
            not math.isfinite(valor) or valor <= 0
            for valor in [self.horas_sesion, self.minutos_inactividad]
        ):
            raise ValueError("La duración de sesión debe ser positiva.")
        if not math.isfinite(self.umbral_facial) or not -1 <= self.umbral_facial <= 1:
            raise ValueError("Umbral facial no válido.")
        if self.voz_habilitada and len(self.clave_voz) < 32:
            raise ValueError("Defina CLAVE_VOZ con al menos 32 caracteres.")

    @classmethod
    def cargar(cls):
        directorio = RAIZ / "data"
        directorio.mkdir(exist_ok=True)
        clave = os.getenv("CLAVE_SESION")
        if not clave:
            ruta = directorio / "session.key"
            if not ruta.exists():
                with ruta.open("x", encoding="utf-8") as archivo:
                    archivo.write(secrets.token_hex(48))
                ruta.chmod(0o600)
            clave = ruta.read_text(encoding="utf-8")
        asistente = os.getenv("ASISTENTE_HABILITADO") == "true"
        return cls(
            clave_sesion=clave,
            horas_sesion=float(os.getenv("HORAS_SESION", "8")),
            minutos_inactividad=float(os.getenv("MINUTOS_INACTIVIDAD", "15")),
            cookie_segura=os.getenv("COOKIE_SEGURA") == "true",
            umbral_facial=float(os.getenv("UMBRAL_FACIAL", "0.363")),
            asistente_habilitado=asistente,
            voz_habilitada=asistente and os.getenv("VOZ_HABILITADA") == "true",
            clave_voz=os.getenv("CLAVE_VOZ", ""),
        )
