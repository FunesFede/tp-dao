"""Préstamos locales e interbibliotecarios, entregas, cancelaciones y devoluciones."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..datos.repositorios import Repositorios
from ..modelo import (MAX_PRESTAMOS_ABIERTOS, CalculadoraSancion, Devolucion, Ejemplar,
                      ErrorNegocio, EstadoEjemplar, EstadoPrestamo, Multa, Prestamo, Sancion, Socio)
from .base import ServicioBase
from .operaciones import ejemplar_quedo_libre, empaquetar, quitar_de_remito_en_preparacion


@dataclass
class ResultadoDevolucion:
    prestamo: Prestamo
    dias_atraso: int
    sancion: Sancion | None
    avisos: list[str]

    def mensaje(self) -> str:
        partes = ["Devolución registrada."]
        if self.sancion:
            partes.append(self.sancion.descripcion() + ".")
        else:
            partes.append("Sin atraso.")
        partes.extend(self.avisos)
        return " ".join(partes)


def validar_socio_para_prestamo(r: Repositorios, socio: Socio, hoy) -> None:
    socio.exigir_habilitado(hoy)
    if r.socios.contar_prestamos_abiertos(socio.id) >= MAX_PRESTAMOS_ABIERTOS:
        raise ErrorNegocio(f"El socio ya tiene {MAX_PRESTAMOS_ABIERTOS} préstamos abiertos")


def crear_prestamo_local(r: Repositorios, socio: Socio, ejemplar: Ejemplar, ahora) -> Prestamo:
    """Préstamo en la propia sede: el socio se lleva el ejemplar en el momento."""
    prestamo = Prestamo.nuevo(socio.id, ejemplar.id, ejemplar.sede_id, ejemplar.sede_id, ahora)
    prestamo.entregar(ahora)
    ejemplar.prestar()
    r.prestamos.crear(prestamo)
    r.ejemplares.actualizar(ejemplar)
    return prestamo


class ServicioPrestamos(ServicioBase):
    def listar(self, estados: tuple[str, ...] | None = None, texto: str = "",
               socio_id: int | None = None) -> list[dict]:
        hoy = self.ahora().date()
        with self._transaccion() as r:
            filas = r.prestamos.listar_resumen(estados, texto, socio_id)
        for fila in filas:
            vence = fila["fecha_vencimiento"]
            en_poder_del_socio = fila["estado"] in (EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO)
            fila["dias_atraso"] = max(0, (hoy - date.fromisoformat(vence)).days) if en_poder_del_socio else 0
        return filas

    def registrar(self, socio_id: int, ejemplar_id: int, sede_origen_id: int, sede_destino_id: int) -> Prestamo:
        ahora = self.ahora()
        with self._transaccion() as r:
            socio = self._obtener(r.socios.obtener_por_id(socio_id), "el socio")
            ejemplar = self._obtener(r.ejemplares.obtener_por_id(ejemplar_id), "el ejemplar")
            origen = self._obtener(r.sedes.obtener_por_id(sede_origen_id), "la sede de origen")
            destino = self._obtener(r.sedes.obtener_por_id(sede_destino_id), "la sede de destino")

            validar_socio_para_prestamo(r, socio, ahora.date())
            origen.exigir_activa()
            destino.exigir_activa()
            if not ejemplar.pertenece_a(origen.id):
                raise ErrorNegocio(f"El ejemplar {ejemplar.codigo_inventario} no pertenece a la sede {origen.nombre}")
            if not ejemplar.esta_en_su_sede():
                raise ErrorNegocio(f"El ejemplar {ejemplar.codigo_inventario} no está físicamente en su sede")
            if not ejemplar.esta_disponible():
                raise ErrorNegocio(f"El ejemplar {ejemplar.codigo_inventario} no está disponible ({ejemplar.estado})")

            if origen.id == destino.id:
                return crear_prestamo_local(r, socio, ejemplar, ahora)

            prestamo = Prestamo.nuevo(socio.id, ejemplar.id, origen.id, destino.id, ahora)
            ejemplar.apartar()
            r.prestamos.crear(prestamo)
            r.ejemplares.actualizar(ejemplar)
            empaquetar(r, ejemplar, prestamo.id, origen.id, destino.id, self.reloj)
            return prestamo

    def entregar(self, prestamo_id: int) -> Prestamo:
        """El socio retira en la sede de destino un ejemplar que llegó por préstamo interbibliotecario."""
        ahora = self.ahora()
        with self._transaccion() as r:
            prestamo = self._obtener(r.prestamos.obtener_por_id(prestamo_id), "el préstamo")
            socio = r.socios.obtener_por_id(prestamo.socio_id)
            socio.exigir_habilitado(ahora.date())
            ejemplar = r.ejemplares.obtener_por_id(prestamo.ejemplar_id)
            prestamo.entregar(ahora)
            ejemplar.prestar()
            r.prestamos.actualizar(prestamo)
            r.ejemplares.actualizar(ejemplar)
            return prestamo

    def cancelar(self, prestamo_id: int) -> str:
        with self._transaccion() as r:
            prestamo = self._obtener(r.prestamos.obtener_por_id(prestamo_id), "el préstamo")
            if prestamo.estado == EstadoPrestamo.EN_TRANSITO:
                raise ErrorNegocio("El ejemplar está viajando; el préstamo se puede cancelar cuando llegue")
            ejemplar = r.ejemplares.obtener_por_id(prestamo.ejemplar_id)
            if prestamo.estado == EstadoPrestamo.SOLICITADO:
                quitar_de_remito_en_preparacion(r, ejemplar.id, f"Anulado al cancelar el préstamo #{prestamo.id}",
                                                self.reloj)
            prestamo.cancelar()
            r.prestamos.actualizar(prestamo)
            if ejemplar.estado == EstadoEjemplar.RESERVADO:
                ejemplar.liberar()
                r.ejemplares.actualizar(ejemplar)
            aviso = ejemplar_quedo_libre(r, ejemplar, self.reloj)
            return "Préstamo cancelado." + (f" {aviso}" if aviso else "")

    def registrar_devolucion(self, prestamo_id: int, sede_recepcion_id: int, estado_fisico: str,
                             observaciones: str | None = None) -> ResultadoDevolucion:
        ahora = self.ahora()
        with self._transaccion() as r:
            prestamo = self._obtener(r.prestamos.obtener_por_id(prestamo_id), "el préstamo")
            sede_recepcion = self._obtener(r.sedes.obtener_por_id(sede_recepcion_id), "la sede de recepción")
            sede_recepcion.exigir_activa()
            socio = r.socios.obtener_por_id(prestamo.socio_id)
            ejemplar = r.ejemplares.obtener_por_id(prestamo.ejemplar_id)

            dias_atraso = prestamo.dias_atraso(ahora.date())
            prestamo.registrar_devolucion(ahora)
            ejemplar.devolver(sede_recepcion.id, estado_fisico)
            r.prestamos.actualizar(prestamo)
            r.ejemplares.actualizar(ejemplar)
            r.devoluciones.crear(Devolucion(prestamo.id, ahora, sede_recepcion.id, estado_fisico,
                                            (observaciones or "").strip() or None))

            # Strategy: la sede de origen del préstamo define cómo se sanciona el atraso
            sede_origen = r.sedes.obtener_por_id(prestamo.sede_origen_id)
            calculadora = CalculadoraSancion(sede_origen.estrategia_sancion())
            sancion = calculadora.calcular(prestamo, socio, ahora)
            if sancion is not None:
                r.sanciones.crear(sancion)
                r.socios.actualizar(socio)   # la suspensión modifica al socio

            avisos = []
            aviso = ejemplar_quedo_libre(r, ejemplar, self.reloj)
            if aviso:
                avisos.append(aviso + ".")
            if ejemplar.estado == EstadoEjemplar.BAJA:
                avisos.append("El ejemplar quedó dado de baja por estar destruido.")
            return ResultadoDevolucion(prestamo, dias_atraso, sancion, avisos)

    def sancion_prevista(self, prestamo_id: int) -> str | None:
        """Describe la sanción que correspondería si el préstamo se devolviera ahora (no guarda nada)."""
        ahora = self.ahora()
        with self._transaccion() as r:
            prestamo = self._obtener(r.prestamos.obtener_por_id(prestamo_id), "el préstamo")
            socio = r.socios.obtener_por_id(prestamo.socio_id)
            sede_origen = r.sedes.obtener_por_id(prestamo.sede_origen_id)
            sancion = CalculadoraSancion(sede_origen.estrategia_sancion()).calcular(prestamo, socio, ahora)
            if sancion is None:
                return None
            return f"{sancion.descripcion()} (política de {sede_origen.nombre})"

    def detalle_devolucion(self, prestamo_id: int) -> dict:
        """Préstamo devuelto, su devolución y las sanciones que generó (solo lectura)."""
        with self._transaccion() as r:
            prestamo = r.prestamos.obtener_por_id(prestamo_id)
            devolucion = r.devoluciones.obtener_resumen_por_prestamo(prestamo_id)
            if prestamo is None or prestamo.estado != EstadoPrestamo.DEVUELTO or devolucion is None:
                raise ErrorNegocio("El préstamo no tiene una devolución registrada")
            resumen = r.prestamos.obtener_resumen(prestamo_id)
            sanciones = r.sanciones.listar_por_prestamo(prestamo_id)
        # El atraso se mide contra la fecha en que se devolvió, no contra hoy
        devolucion["dias_atraso"] = prestamo.dias_atraso(prestamo.fecha_devolucion.date())
        return {
            "prestamo": resumen,
            "devolucion": devolucion,
            "sanciones": [{"descripcion": s.descripcion(), "pagada": s.pagada if isinstance(s, Multa) else None}
                          for s in sanciones],
        }

    def actualizar_vencimientos(self) -> int:
        """Marca como vencidos los préstamos activos cuya fecha ya pasó."""
        hoy = self.ahora().date()
        with self._transaccion() as r:
            vencidos = r.prestamos.listar_activos_vencidos(hoy)
            for prestamo in vencidos:
                prestamo.marcar_vencido(hoy)
                r.prestamos.actualizar(prestamo)
            return len(vencidos)
