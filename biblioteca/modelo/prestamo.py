from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .excepciones import ErrorNegocio


class TipoPrestamo:
    LOCAL = "LOCAL"
    INTER = "INTER"


class EstadoPrestamo:
    SOLICITADO = "SOLICITADO"
    EN_TRANSITO = "EN_TRANSITO"
    LISTO_PARA_RETIRO = "LISTO_PARA_RETIRO"
    ACTIVO = "ACTIVO"
    VENCIDO = "VENCIDO"
    DEVUELTO = "DEVUELTO"
    CANCELADO = "CANCELADO"
    ABIERTOS = (SOLICITADO, EN_TRANSITO, LISTO_PARA_RETIRO, ACTIVO, VENCIDO)
    CERRADOS = (DEVUELTO, CANCELADO)
    TODOS = ABIERTOS + CERRADOS


# Reglas de negocio definidas por el equipo
DIAS_PLAZO = {TipoPrestamo.LOCAL: 14, TipoPrestamo.INTER: 21}
MAX_PRESTAMOS_ABIERTOS = 3


@dataclass
class Prestamo:
    socio_id: int
    ejemplar_id: int
    tipo: str
    sede_origen_id: int
    sede_destino_id: int
    fecha_solicitud: datetime
    estado: str = EstadoPrestamo.SOLICITADO
    fecha_inicio: datetime | None = None
    fecha_vencimiento: date | None = None
    fecha_devolucion: datetime | None = None
    id: int | None = None

    def __post_init__(self):
        if self.tipo == TipoPrestamo.LOCAL and self.sede_origen_id != self.sede_destino_id:
            raise ErrorNegocio("Un préstamo local se retira en la misma sede de origen")
        if self.tipo == TipoPrestamo.INTER and self.sede_origen_id == self.sede_destino_id:
            raise ErrorNegocio("Un préstamo interbibliotecario requiere sedes distintas")

    @classmethod
    def nuevo(cls, socio_id: int, ejemplar_id: int, sede_origen_id: int, sede_destino_id: int,
              ahora: datetime) -> Prestamo:
        tipo = TipoPrestamo.LOCAL if sede_origen_id == sede_destino_id else TipoPrestamo.INTER
        return cls(socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id, ahora)

    # --- consultas -----------------------------------------------------------
    def es_interbibliotecario(self) -> bool:
        return self.tipo == TipoPrestamo.INTER

    def esta_abierto(self) -> bool:
        return self.estado in EstadoPrestamo.ABIERTOS

    @property
    def dias_plazo(self) -> int:
        return DIAS_PLAZO[self.tipo]

    def dias_atraso(self, fecha: date) -> int:
        if self.fecha_vencimiento is None:
            return 0
        return max(0, (fecha - self.fecha_vencimiento).days)

    # --- transiciones --------------------------------------------------------
    def _exigir(self, estados: tuple[str, ...], accion: str) -> None:
        if self.estado not in estados:
            raise ErrorNegocio(f"No se puede {accion} un préstamo en estado {self.estado}")

    def marcar_en_transito(self) -> None:
        self._exigir((EstadoPrestamo.SOLICITADO,), "despachar")
        self.estado = EstadoPrestamo.EN_TRANSITO

    def marcar_listo_para_retiro(self) -> None:
        self._exigir((EstadoPrestamo.EN_TRANSITO,), "marcar listo para retiro")
        self.estado = EstadoPrestamo.LISTO_PARA_RETIRO

    def entregar(self, ahora: datetime) -> None:
        """El socio retira el ejemplar: empieza a correr el plazo."""
        esperado = EstadoPrestamo.SOLICITADO if self.tipo == TipoPrestamo.LOCAL else EstadoPrestamo.LISTO_PARA_RETIRO
        self._exigir((esperado,), "entregar")
        self.estado = EstadoPrestamo.ACTIVO
        self.fecha_inicio = ahora
        self.fecha_vencimiento = ahora.date() + timedelta(days=self.dias_plazo)

    def cancelar(self) -> None:
        self._exigir((EstadoPrestamo.SOLICITADO, EstadoPrestamo.EN_TRANSITO,
                      EstadoPrestamo.LISTO_PARA_RETIRO), "cancelar")
        self.estado = EstadoPrestamo.CANCELADO

    def marcar_vencido(self, hoy: date) -> bool:
        if self.estado == EstadoPrestamo.ACTIVO and self.fecha_vencimiento < hoy:
            self.estado = EstadoPrestamo.VENCIDO
            return True
        return False

    def registrar_devolucion(self, ahora: datetime) -> None:
        self._exigir((EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO), "devolver")
        self.estado = EstadoPrestamo.DEVUELTO
        self.fecha_devolucion = ahora


@dataclass
class Devolucion:
    prestamo_id: int
    fecha: datetime
    sede_recepcion_id: int
    estado_fisico: str
    observaciones: str | None = None
    id: int | None = None
