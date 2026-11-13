from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .excepciones import ErrorNegocio


class EstadoReserva:
    PENDIENTE = "PENDIENTE"
    ASIGNADA = "ASIGNADA"
    CUMPLIDA = "CUMPLIDA"
    CANCELADA = "CANCELADA"
    EXPIRADA = "EXPIRADA"
    VIGENTES = (PENDIENTE, ASIGNADA)


DIAS_PARA_RETIRAR = 3


@dataclass
class Reserva:
    """Reserva de un título (no de un ejemplar) para retirar en una sede."""
    socio_id: int
    libro_id: int
    sede_retiro_id: int
    fecha_reserva: datetime
    estado: str = EstadoReserva.PENDIENTE
    ejemplar_asignado_id: int | None = None
    fecha_expiracion: date | None = None
    id: int | None = None

    def _exigir(self, estados: tuple[str, ...], accion: str) -> None:
        if self.estado not in estados:
            raise ErrorNegocio(f"No se puede {accion} una reserva en estado {self.estado}")

    def asignar(self, ejemplar_id: int, hoy: date) -> None:
        self._exigir((EstadoReserva.PENDIENTE,), "asignar")
        self.estado = EstadoReserva.ASIGNADA
        self.ejemplar_asignado_id = ejemplar_id
        self.fecha_expiracion = hoy + timedelta(days=DIAS_PARA_RETIRAR)

    def cumplir(self, hoy: date) -> None:
        self._exigir((EstadoReserva.ASIGNADA,), "retirar")
        if self.fecha_expiracion < hoy:
            raise ErrorNegocio(f"El plazo para retirar la reserva venció el {self.fecha_expiracion:%d/%m/%Y}")
        self.estado = EstadoReserva.CUMPLIDA

    def cancelar(self) -> None:
        self._exigir(EstadoReserva.VIGENTES, "cancelar")
        self.estado = EstadoReserva.CANCELADA

    def expirar(self, hoy: date) -> bool:
        if self.estado == EstadoReserva.ASIGNADA and self.fecha_expiracion < hoy:
            self.estado = EstadoReserva.EXPIRADA
            return True
        return False
