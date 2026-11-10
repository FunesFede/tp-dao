"""Casos de uso. La interfaz solo habla con estas clases."""
from .base import Reloj, RelojManual
from .catalogo import ServicioCatalogo
from .consulta_socio import ServicioConsultaSocio
from .prestamos import ResultadoDevolucion, ServicioPrestamos
from .remitos_reservas import ServicioRemitos, ServicioReservas
from .reportes import ServicioReportes
from .sedes_socios import ServicioSedes, ServicioSocios


class Servicios:
    """Punto de acceso único a los servicios, compartiendo el mismo reloj."""

    def __init__(self, reloj: Reloj | None = None):
        self.reloj = reloj or Reloj()
        self.sedes = ServicioSedes(self.reloj)
        self.socios = ServicioSocios(self.reloj)
        self.catalogo = ServicioCatalogo(self.reloj)
        self.prestamos = ServicioPrestamos(self.reloj)
        self.remitos = ServicioRemitos(self.reloj)
        self.reservas = ServicioReservas(self.reloj)
        self.reportes = ServicioReportes(self.reloj)
        self.consulta_socio = ServicioConsultaSocio(self.reloj)

    def procesar_vencimientos(self) -> str:
        """Marca préstamos vencidos y expira reservas no retiradas. Se llama al abrir la aplicación."""
        vencidos = self.prestamos.actualizar_vencimientos()
        expiradas = self.reservas.expirar_vencidas()
        return f"{vencidos} préstamo(s) pasaron a vencidos y {expiradas} reserva(s) expiraron."
