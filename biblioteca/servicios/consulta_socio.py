"""Consultas del socio sobre sus propios datos (modo de consulta para socios).

Cada método recibe el `socio_id` del socio que ingresó y nunca devuelve datos de otro socio.
Las operaciones que el socio puede hacer (reservar y cancelar sus reservas) se delegan en
ServicioReservas para no duplicar sus validaciones.
"""
from __future__ import annotations

from ..modelo import MAX_PRESTAMOS_ABIERTOS, ErrorNegocio, EstadoPrestamo, Reserva, Socio
from .base import ServicioBase
from .prestamos import ServicioPrestamos
from .remitos_reservas import ServicioReservas


class ServicioConsultaSocio(ServicioBase):
    def __init__(self, reloj=None):
        super().__init__(reloj)
        self._prestamos = ServicioPrestamos(self.reloj)
        self._reservas = ServicioReservas(self.reloj)

    def ingresar(self, dni: str) -> Socio:
        """Busca al socio por DNI. Es una consulta, no una autenticación: no hay contraseña."""
        dni = (dni or "").strip().replace(".", "")   # misma normalización que Socio
        with self._transaccion() as r:
            socio = r.socios.obtener_por_dni(dni) if dni else None
        if socio is None:
            raise ErrorNegocio("No hay un socio registrado con ese DNI")
        return socio

    def situacion(self, socio_id: int) -> dict:
        hoy = self.ahora().date()
        with self._transaccion() as r:
            socio = self._obtener(r.socios.obtener_por_id(socio_id), "el socio")
            prestamos_abiertos = r.socios.contar_prestamos_abiertos(socio_id)
            sanciones = r.sanciones.listar_resumen(socio_id)
        multas = [s for s in sanciones if s["tipo"] == "MONETARIA" and not s["pagada"]]
        return {
            "socio": socio,
            "situacion": socio.motivo_bloqueo(hoy) or "habilitado",
            "prestamos_abiertos": prestamos_abiertos,
            "max_prestamos": MAX_PRESTAMOS_ABIERTOS,
            "multas_impagas": multas,
            "deuda": sum(s["monto"] for s in multas),
        }

    def prestamos(self, socio_id: int, abiertos: bool = True) -> list[dict]:
        estados = EstadoPrestamo.ABIERTOS if abiertos else EstadoPrestamo.CERRADOS
        return self._prestamos.listar(estados, socio_id=socio_id)

    def reservas(self, socio_id: int) -> list[dict]:
        return self._reservas.listar(socio_id=socio_id)

    def reservar(self, socio_id: int, libro_id: int, sede_retiro_id: int) -> Reserva:
        return self._reservas.crear(socio_id, libro_id, sede_retiro_id)

    def cancelar_reserva(self, socio_id: int, reserva_id: int) -> str:
        with self._transaccion() as r:
            reserva = self._obtener(r.reservas.obtener_por_id(reserva_id), "la reserva")
        if reserva.socio_id != socio_id:
            raise ErrorNegocio("La reserva no pertenece al socio")
        return self._reservas.cancelar(reserva_id)
