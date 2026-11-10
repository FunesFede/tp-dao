"""Agrupa los DAO que comparten una misma conexión (y por lo tanto una misma transacción)."""
from __future__ import annotations

import sqlite3

from .catalogo_dao import EjemplarDAO, LibroDAO
from .prestamo_dao import DevolucionDAO, PrestamoDAO
from .remito_dao import RemitoDAO
from .reserva_dao import ReservaDAO
from .sancion_dao import SancionDAO
from .sede_dao import SedeDAO
from .socio_dao import SocioDAO


class Repositorios:
    def __init__(self, conexion: sqlite3.Connection):
        self.conexion = conexion
        self.sedes = SedeDAO(conexion)
        self.socios = SocioDAO(conexion)
        self.libros = LibroDAO(conexion)
        self.ejemplares = EjemplarDAO(conexion)
        self.prestamos = PrestamoDAO(conexion)
        self.devoluciones = DevolucionDAO(conexion)
        self.reservas = ReservaDAO(conexion)
        self.remitos = RemitoDAO(conexion)
        self.sanciones = SancionDAO(conexion)
