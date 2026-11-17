"""Casos de uso. La interfaz solo habla con estas clases."""
from ..datos.conexion import inicializar_base
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

    @staticmethod
    def preparar_base() -> None:
        """Crea las tablas si la base todavía no existe. Se llama al abrir la aplicación."""
        inicializar_base()

    def procesar_vencimientos(self) -> str:
        """Marca préstamos vencidos, expira reservas y cancela préstamos no retirados. Se llama al abrir la app."""
        vencidos = self.prestamos.actualizar_vencimientos()
        expiradas = self.reservas.expirar_vencidas()
        no_retirados = self.prestamos.cancelar_no_retirados()
        return (f"{vencidos} préstamo(s) pasaron a vencidos, {expiradas} reserva(s) expiraron y "
                f"{no_retirados} préstamo(s) interbibliotecario(s) se cancelaron por no retirarse a tiempo.")
