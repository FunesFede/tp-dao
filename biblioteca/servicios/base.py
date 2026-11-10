"""Infraestructura común de los servicios: reloj y manejo de transacciones."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

from ..datos.conexion import obtener_conexion
from ..datos.repositorios import Repositorios
from ..modelo import ErrorNegocio


class Reloj:
    """Fuente de la fecha y hora actual. Se reemplaza en el seed y las pruebas."""

    def ahora(self) -> datetime:
        return datetime.now().replace(microsecond=0)


class RelojManual(Reloj):
    def __init__(self, inicio: datetime):
        self._actual = inicio.replace(microsecond=0)

    def ahora(self) -> datetime:
        return self._actual

    def fijar(self, momento: datetime) -> None:
        self._actual = momento.replace(microsecond=0)

    def avanzar(self, **delta) -> datetime:
        self._actual += timedelta(**delta)
        return self._actual


# Mensajes para las restricciones UNIQUE de la base
_MENSAJES_UNICIDAD = {
    "socio.dni": "Ya existe un socio con ese DNI",
    "socio.email": "Ya existe un socio con ese email",
    "libro.isbn": "Ya existe un libro con ese ISBN",
    "ejemplar.codigo_inventario": "Ya existe un ejemplar con ese código de inventario",
    "sede.nombre": "Ya existe una sede con ese nombre",
    "reserva.socio_id": "El socio ya tiene una reserva vigente de ese libro",
    "prestamo.ejemplar_id": "El ejemplar ya tiene un préstamo abierto",
}


def _traducir_error_integridad(error: sqlite3.IntegrityError) -> ErrorNegocio:
    texto = str(error)
    for clave, mensaje in _MENSAJES_UNICIDAD.items():
        if clave in texto:
            return ErrorNegocio(mensaje)
    return ErrorNegocio(f"Los datos no cumplen una restricción de la base: {texto}")


class ServicioBase:
    def __init__(self, reloj: Reloj | None = None):
        self.reloj = reloj or Reloj()

    def ahora(self) -> datetime:
        return self.reloj.ahora()

    @contextmanager
    def _transaccion(self) -> Iterator[Repositorios]:
        """Abre una conexión, entrega los DAO y confirma o deshace todo junto."""
        conexion = obtener_conexion()
        try:
            yield Repositorios(conexion)
            conexion.commit()
        except sqlite3.IntegrityError as error:
            conexion.rollback()
            raise _traducir_error_integridad(error) from error
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    @staticmethod
    def _obtener(entidad, nombre: str):
        if entidad is None:
            raise ErrorNegocio(f"No existe {nombre}")
        return entidad
