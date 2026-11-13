"""Operaciones compartidas entre servicios.

Reciben los DAO de la transacción en curso (Repositorios) para que todo lo que hacen se
confirme o se deshaga junto con la operación que las llamó.
"""
from __future__ import annotations

from datetime import date

from ..datos.repositorios import Repositorios
from ..modelo import Ejemplar, ErrorNegocio, Remito
from .base import Reloj


def empaquetar(r: Repositorios, ejemplar: Ejemplar, prestamo_id: int | None,
               sede_origen_id: int, sede_destino_id: int, reloj: Reloj) -> Remito:
    """Agrega el ejemplar al remito en preparación entre las dos sedes (o crea uno nuevo)."""
    for sede_id in (sede_origen_id, sede_destino_id):
        sede = r.sedes.obtener_por_id(sede_id)
        sede.exigir_activa()
    if ejemplar.sede_actual_id != sede_origen_id:
        raise ErrorNegocio(f"El ejemplar {ejemplar.codigo_inventario} no está en la sede de origen del envío")
    en_curso = r.remitos.obtener_en_curso_por_ejemplar(ejemplar.id)
    if en_curso is not None:
        raise ErrorNegocio(f"El ejemplar {ejemplar.codigo_inventario} ya viaja en el remito {en_curso.numero}")

    remito = r.remitos.obtener_en_preparacion(sede_origen_id, sede_destino_id)
    if remito is None:
        remito = Remito(r.remitos.siguiente_numero(), sede_origen_id, sede_destino_id, reloj=reloj.ahora)
        remito.agregar_ejemplar(ejemplar.id, prestamo_id)
        r.remitos.crear(remito)
    else:
        remito.agregar_ejemplar(ejemplar.id, prestamo_id)
        r.remitos.guardar(remito)
    return remito


def quitar_de_remito_en_preparacion(r: Repositorios, ejemplar_id: int, motivo: str, reloj: Reloj) -> str | None:
    """Saca el ejemplar del remito en preparación en que espera; si el remito queda vacío, lo anula.

    Devuelve el número del remito, o None si el ejemplar no esperaba en ninguno.
    """
    remito = r.remitos.obtener_en_curso_por_ejemplar(ejemplar_id)
    if remito is None:
        return None
    remito.quitar_ejemplar(ejemplar_id)   # solo se puede si el remito sigue en preparación
    if not remito.ejemplares:   # sin ejemplares el remito no tiene sentido: se anula
        remito.reloj = reloj.ahora
        remito.anular(remito.sede_origen_id, motivo)
    r.remitos.guardar(remito)
    return remito.numero


def asignar_reservas(r: Repositorios, libro_id: int, sede_id: int, hoy: date) -> int:
    """Asigna ejemplares disponibles de la sede a las reservas pendientes, por orden de llegada."""
    asignadas = 0
    pendientes = r.reservas.listar_pendientes(libro_id, sede_id)
    disponibles = r.ejemplares.listar_disponibles_en_su_sede(libro_id, sede_id)
    for reserva, ejemplar in zip(pendientes, disponibles):
        ejemplar.apartar()
        reserva.asignar(ejemplar.id, hoy)
        r.ejemplares.actualizar(ejemplar)
        r.reservas.actualizar(reserva)
        asignadas += 1
    return asignadas


def ejemplar_quedo_libre(r: Repositorios, ejemplar: Ejemplar, reloj: Reloj) -> str | None:
    """Decide qué pasa con un ejemplar que quedó disponible.

    Si está en su sede, atiende las reservas pendientes; si quedó en otra sede, lo empaqueta
    en un remito de retorno. Devuelve un mensaje para el usuario, o None.
    """
    if not ejemplar.esta_disponible():
        return None
    if ejemplar.esta_en_su_sede():
        if asignar_reservas(r, ejemplar.libro_id, ejemplar.sede_id, reloj.ahora().date()):
            return f"El ejemplar {ejemplar.codigo_inventario} quedó asignado a una reserva pendiente"
        return None
    remito = empaquetar(r, ejemplar, None, ejemplar.sede_actual_id, ejemplar.sede_id, reloj)
    return f"El ejemplar {ejemplar.codigo_inventario} se agregó al remito de retorno {remito.numero}"
