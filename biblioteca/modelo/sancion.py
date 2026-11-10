"""Sanciones por atraso en la devolución: patrón Strategy.

Roles del patrón según la cátedra:
- Estrategia abstracta: EstrategiaSancion
- Estrategias concretas: SancionMonetaria, SancionSuspension
- Contexto: CalculadoraSancion, que recibe la estrategia y la invoca sin conocer la clase concreta.

La selección es externa: la estrategia la arma la sede de origen del préstamo a partir de su
configuración (Sede.estrategia_sancion()) y el servicio de préstamos se la pasa a la calculadora.

Cada estrategia produce un objeto Sancion distinto: una Multa (monto a pagar) o una
Suspension (el socio no puede pedir préstamos hasta una fecha).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from .excepciones import ErrorNegocio

if TYPE_CHECKING:
    from .prestamo import Prestamo
    from .socio import Socio


def pesos(monto: float) -> str:
    """Formato local: $1.234,50"""
    return "$" + f"{monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class MotivoSancion:
    ATRASO = "ATRASO"
    DANIO = "DANIO"
    PERDIDA = "PERDIDA"


class TipoSancion:
    MONETARIA = "MONETARIA"
    SUSPENSION = "SUSPENSION"


# ---------------------------------------------------------------------------
# Sanciones (lo que producen las estrategias)
# ---------------------------------------------------------------------------
@dataclass
class Sancion(ABC):
    prestamo_id: int
    socio_id: int
    dias_atraso: int
    fecha: datetime
    motivo: str = MotivoSancion.ATRASO
    id: int | None = None

    @property
    @abstractmethod
    def tipo(self) -> str: ...

    @abstractmethod
    def descripcion(self) -> str: ...


@dataclass
class Multa(Sancion):
    monto: float = 0.0
    pagada: bool = False

    @property
    def tipo(self) -> str:
        return TipoSancion.MONETARIA

    def pagar(self) -> None:
        if self.pagada:
            raise ErrorNegocio("La multa ya estaba pagada")
        self.pagada = True

    def descripcion(self) -> str:
        return f"Multa de {pesos(self.monto)} por {self.dias_atraso} día(s) de atraso"


@dataclass
class Suspension(Sancion):
    suspendido_hasta: date | None = None

    @property
    def tipo(self) -> str:
        return TipoSancion.SUSPENSION

    def descripcion(self) -> str:
        return (f"Suspensión hasta el {self.suspendido_hasta:%d/%m/%Y} "
                f"por {self.dias_atraso} día(s) de atraso")


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------
class EstrategiaSancion(ABC):
    @abstractmethod
    def aplicar(self, prestamo: Prestamo, socio: Socio, dias_atraso: int, ahora: datetime) -> Sancion:
        """Crea la sanción para un atraso de `dias_atraso` días (siempre > 0)."""

    @abstractmethod
    def descripcion(self) -> str: ...


class SancionMonetaria(EstrategiaSancion):
    def __init__(self, monto_por_dia: float):
        if monto_por_dia is None or monto_por_dia <= 0:
            raise ErrorNegocio("El monto por día de atraso debe ser mayor a cero")
        self.monto_por_dia = monto_por_dia

    def aplicar(self, prestamo, socio, dias_atraso, ahora):
        return Multa(prestamo_id=prestamo.id, socio_id=socio.id, dias_atraso=dias_atraso,
                     fecha=ahora, monto=round(dias_atraso * self.monto_por_dia, 2))

    def descripcion(self):
        return f"Multa de {pesos(self.monto_por_dia)} por día de atraso"


class SancionSuspension(EstrategiaSancion):
    def __init__(self, factor: int):
        if factor is None or factor <= 0:
            raise ErrorNegocio("El factor de suspensión debe ser mayor a cero")
        self.factor = factor

    def aplicar(self, prestamo, socio, dias_atraso, ahora):
        hasta = ahora.date() + timedelta(days=dias_atraso * self.factor)
        socio.suspender_hasta(hasta)
        return Suspension(prestamo_id=prestamo.id, socio_id=socio.id, dias_atraso=dias_atraso,
                          fecha=ahora, suspendido_hasta=hasta)

    def descripcion(self):
        return f"Suspensión de {self.factor} día(s) por cada día de atraso"


class CalculadoraSancion:
    """Contexto del Strategy."""

    def __init__(self, estrategia: EstrategiaSancion):
        self.estrategia = estrategia

    def cambiar_estrategia(self, estrategia: EstrategiaSancion) -> None:
        self.estrategia = estrategia

    def calcular(self, prestamo: Prestamo, socio: Socio, ahora: datetime) -> Sancion | None:
        """Devuelve la sanción correspondiente, o None si la devolución no tiene atraso."""
        dias = prestamo.dias_atraso(ahora.date())
        if dias <= 0:
            return None
        return self.estrategia.aplicar(prestamo, socio, dias, ahora)
