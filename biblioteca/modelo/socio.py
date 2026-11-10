from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .excepciones import ErrorNegocio


@dataclass
class Socio:
    dni: str
    nombre: str
    apellido: str
    sede_id: int
    email: str | None = None
    telefono: str | None = None
    suspendido_hasta: date | None = None
    inhabilitado_manual: bool = False
    motivo_inhabilitacion: str | None = None
    fecha_alta: date | None = None
    id: int | None = None

    def __post_init__(self):
        self.dni = (self.dni or "").strip().replace(".", "")
        self.nombre = (self.nombre or "").strip()
        self.apellido = (self.apellido or "").strip()
        self.email = (self.email or "").strip() or None
        if not self.dni.isdigit() or not 7 <= len(self.dni) <= 8:
            raise ErrorNegocio("El DNI debe tener 7 u 8 dígitos")
        if not self.nombre or not self.apellido:
            raise ErrorNegocio("Nombre y apellido son obligatorios")
        if self.email and "@" not in self.email:
            raise ErrorNegocio("El email del socio no es válido")

    @property
    def nombre_completo(self) -> str:
        return f"{self.apellido}, {self.nombre}"

    def esta_suspendido(self, hoy: date) -> bool:
        return self.suspendido_hasta is not None and self.suspendido_hasta > hoy

    def esta_inhabilitado(self, hoy: date) -> bool:
        return self.inhabilitado_manual or self.esta_suspendido(hoy)

    def motivo_bloqueo(self, hoy: date) -> str | None:
        if self.inhabilitado_manual:
            return f"inhabilitado: {self.motivo_inhabilitacion}"
        if self.esta_suspendido(hoy):
            return f"suspendido hasta el {self.suspendido_hasta:%d/%m/%Y}"
        return None

    def exigir_habilitado(self, hoy: date) -> None:
        motivo = self.motivo_bloqueo(hoy)
        if motivo:
            raise ErrorNegocio(f"El socio {self.nombre_completo} está {motivo}")

    def suspender_hasta(self, fecha: date) -> None:
        """Extiende la suspensión; nunca la acorta si ya había una más larga."""
        if self.suspendido_hasta is None or fecha > self.suspendido_hasta:
            self.suspendido_hasta = fecha

    def inhabilitar(self, motivo: str) -> None:
        motivo = (motivo or "").strip()
        if not motivo:
            raise ErrorNegocio("Indique el motivo de la inhabilitación")
        self.inhabilitado_manual = True
        self.motivo_inhabilitacion = motivo

    def habilitar(self) -> None:
        self.inhabilitado_manual = False
        self.motivo_inhabilitacion = None
