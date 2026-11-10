from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .excepciones import ErrorNegocio
from .sancion import EstrategiaSancion, SancionMonetaria, SancionSuspension


class PoliticaSancion:
    MONETARIA = "MONETARIA"
    SUSPENSION = "SUSPENSION"
    TODAS = (MONETARIA, SUSPENSION)


@dataclass
class Sede:
    nombre: str
    direccion: str
    telefono: str | None = None
    email: str | None = None
    horario: str | None = None
    politica_sancion: str = PoliticaSancion.MONETARIA
    monto_por_dia: float | None = None
    factor_suspension: int | None = None
    activa: bool = True
    fecha_baja: date | None = None
    id: int | None = None

    def __post_init__(self):
        self.validar()

    def validar(self) -> None:
        self.nombre = (self.nombre or "").strip()
        self.direccion = (self.direccion or "").strip()
        if not self.nombre:
            raise ErrorNegocio("El nombre de la sede es obligatorio")
        if not self.direccion:
            raise ErrorNegocio("La dirección de la sede es obligatoria")
        if self.email and "@" not in self.email:
            raise ErrorNegocio("El email de la sede no es válido")
        if self.politica_sancion == PoliticaSancion.MONETARIA:
            if not self.monto_por_dia or self.monto_por_dia <= 0:
                raise ErrorNegocio("La política monetaria requiere un monto por día mayor a cero")
            self.factor_suspension = None
        elif self.politica_sancion == PoliticaSancion.SUSPENSION:
            if not self.factor_suspension or self.factor_suspension <= 0:
                raise ErrorNegocio("La política de suspensión requiere un factor mayor a cero")
            self.monto_por_dia = None
        else:
            raise ErrorNegocio(f"Política de sanción desconocida: {self.politica_sancion}")

    def dar_de_baja(self, fecha: date) -> None:
        if not self.activa:
            raise ErrorNegocio(f"La sede {self.nombre} ya está dada de baja")
        self.activa = False
        self.fecha_baja = fecha

    def reactivar(self) -> None:
        if self.activa:
            raise ErrorNegocio(f"La sede {self.nombre} ya está activa")
        self.activa = True
        self.fecha_baja = None

    def exigir_activa(self) -> None:
        if not self.activa:
            raise ErrorNegocio(f"La sede {self.nombre} está dada de baja")

    def estrategia_sancion(self) -> EstrategiaSancion:
        """Arma la estrategia de sanción configurada para esta sede (selección externa del Strategy)."""
        if self.politica_sancion == PoliticaSancion.MONETARIA:
            return SancionMonetaria(self.monto_por_dia)
        return SancionSuspension(self.factor_suspension)
