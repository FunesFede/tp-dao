from __future__ import annotations

from ..modelo import ErrorNegocio, EstadoReserva, Remito, Reserva
from .base import ServicioBase
from .observadores import ActualizadorEjemplares, ActualizadorPrestamos
from .operaciones import asignar_reservas, ejemplar_quedo_libre
from .prestamos import crear_prestamo_local, validar_socio_para_prestamo


class ServicioRemitos(ServicioBase):
    def listar(self, solo_en_curso: bool = False) -> list[dict]:
        with self._transaccion() as r:
            return r.remitos.listar_resumen(solo_en_curso)

    def detalle(self, remito_id: int) -> dict:
        with self._transaccion() as r:
            remito = self._obtener(r.remitos.obtener_por_id(remito_id), "el remito")
            transito = remito.tiempo_en_transito()
            return {
                "remito": remito,
                "ejemplares": r.remitos.listar_detalle(remito_id),
                "movimientos": r.remitos.listar_movimientos(remito_id),
                "tiempo_en_transito": transito,
            }

    def despachar(self, remito_id: int) -> str:
        def operacion(remito: Remito, r):
            for sede_id in (remito.sede_origen_id, remito.sede_destino_id):
                r.sedes.obtener_por_id(sede_id).exigir_activa()
            remito.despachar(remito.sede_origen_id)
        return self._operar(remito_id, operacion, "Remito despachado")

    def registrar_transito(self, remito_id: int, observacion: str) -> str:
        return self._operar(remito_id, lambda remito, r: remito.registrar_transito(None, observacion),
                            "Movimiento de tránsito registrado")

    def recibir(self, remito_id: int, incidencias: dict[int, str] | None = None) -> str:
        return self._operar(remito_id, lambda remito, r: remito.recibir(remito.sede_destino_id, incidencias),
                            "Remito recibido")

    def declarar_extravio(self, remito_id: int, observacion: str = "") -> str:
        return self._operar(remito_id, lambda remito, r: remito.declarar_extravio(None, observacion),
                            "Remito declarado extraviado")

    def anular(self, remito_id: int, motivo: str = "") -> str:
        return self._operar(remito_id, lambda remito, r: remito.anular(remito.sede_origen_id, motivo),
                            "Remito anulado")

    def _operar(self, remito_id: int, operacion, mensaje: str) -> str:
        """Carga el remito, suscribe los observadores, aplica la operación y guarda todo junto."""
        with self._transaccion() as r:
            remito = self._obtener(r.remitos.obtener_por_id(remito_id), "el remito")
            remito.reloj = self.reloj.ahora
            ejemplares = ActualizadorEjemplares(r, self.reloj)
            remito.suscribir(ejemplares)
            remito.suscribir(ActualizadorPrestamos(r))
            operacion(remito, r)
            r.remitos.guardar(remito)
            return " ".join([f"{mensaje}: {remito.numero}."] + ejemplares.mensajes)


class ServicioReservas(ServicioBase):
    def listar(self, solo_vigentes: bool = False, socio_id: int | None = None) -> list[dict]:
        with self._transaccion() as r:
            return r.reservas.listar_resumen(solo_vigentes, socio_id)

    def crear(self, socio_id: int, libro_id: int, sede_retiro_id: int) -> Reserva:
        ahora = self.ahora()
        with self._transaccion() as r:
            socio = self._obtener(r.socios.obtener_por_id(socio_id), "el socio")
            libro = self._obtener(r.libros.obtener_por_id(libro_id), "el libro")
            sede = self._obtener(r.sedes.obtener_por_id(sede_retiro_id), "la sede")
            # Si no puede llevarse un libro más, tampoco puede reservarlo
            validar_socio_para_prestamo(r, socio, ahora.date())
            sede.exigir_activa()
            if r.ejemplares.contar_de_sede(libro.id, sede.id) == 0:
                raise ErrorNegocio(f"La sede {sede.nombre} no tiene ejemplares de «{libro.titulo}». "
                                   "Para traerlo de otra sede, registre un préstamo interbibliotecario.")
            reserva = Reserva(socio.id, libro.id, sede.id, ahora)
            r.reservas.crear(reserva)
            asignar_reservas(r, libro.id, sede.id, ahora.date())
            return r.reservas.obtener_por_id(reserva.id)

    def retirar(self, reserva_id: int) -> str:
        """El socio retira el ejemplar apartado: la reserva se cumple y nace un préstamo local."""
        ahora = self.ahora()
        with self._transaccion() as r:
            reserva = self._obtener(r.reservas.obtener_por_id(reserva_id), "la reserva")
            if reserva.estado != EstadoReserva.ASIGNADA:
                raise ErrorNegocio("La reserva todavía no tiene un ejemplar asignado")
            socio = r.socios.obtener_por_id(reserva.socio_id)
            r.sedes.obtener_por_id(reserva.sede_retiro_id).exigir_activa()
            validar_socio_para_prestamo(r, socio, ahora.date())
            ejemplar = r.ejemplares.obtener_por_id(reserva.ejemplar_asignado_id)
            reserva.cumplir(ahora.date())
            r.reservas.actualizar(reserva)
            prestamo = crear_prestamo_local(r, socio, ejemplar, ahora)
            return f"Reserva retirada. Préstamo #{prestamo.id}, vence el {prestamo.fecha_vencimiento:%d/%m/%Y}."

    def cancelar(self, reserva_id: int) -> str:
        with self._transaccion() as r:
            reserva = self._obtener(r.reservas.obtener_por_id(reserva_id), "la reserva")
            ejemplar_id = reserva.ejemplar_asignado_id if reserva.estado == EstadoReserva.ASIGNADA else None
            reserva.cancelar()
            r.reservas.actualizar(reserva)
            return "Reserva cancelada." + self._liberar(r, ejemplar_id)

    def expirar_vencidas(self) -> int:
        """Las reservas asignadas que no se retiraron a tiempo expiran y liberan el ejemplar."""
        hoy = self.ahora().date()
        with self._transaccion() as r:
            vencidas = r.reservas.listar_asignadas_vencidas(hoy)
            for reserva in vencidas:
                reserva.expirar(hoy)
                r.reservas.actualizar(reserva)
                self._liberar(r, reserva.ejemplar_asignado_id)
            return len(vencidas)

    def _liberar(self, r, ejemplar_id: int | None) -> str:
        if ejemplar_id is None:
            return ""
        ejemplar = r.ejemplares.obtener_por_id(ejemplar_id)
        ejemplar.liberar()
        r.ejemplares.actualizar(ejemplar)
        aviso = ejemplar_quedo_libre(r, ejemplar, self.reloj)
        return f" {aviso}." if aviso else ""
