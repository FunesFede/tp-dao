import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from biblioteca.datos import conexion
from biblioteca.datos.conexion import configurar_ruta, inicializar_base
from biblioteca.servicios import RelojManual, Servicios


@pytest.fixture
def cx():
    """Base en memoria con el esquema cargado, para probar las restricciones."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(Path(conexion.RUTA_SCHEMA).read_text(encoding="utf-8"))
    yield c
    c.close()


@pytest.fixture
def base(tmp_path):
    ruta_anterior = conexion.ruta_actual()
    configurar_ruta(tmp_path / "prueba.db")
    inicializar_base()
    yield
    configurar_ruta(ruta_anterior)


@pytest.fixture
def reloj():
    return RelojManual(datetime(2026, 9, 1, 10, 0))


@pytest.fixture
def s(base, reloj):
    return Servicios(reloj)


@pytest.fixture
def red(s):
    """Tres sedes, dos socios, un libro con un ejemplar en Centro y otro en Norte."""
    centro = s.sedes.crear("Centro", "Av. 1", None, None, None, "MONETARIA", 100)
    norte = s.sedes.crear("Norte", "Av. 2", None, None, None, "SUSPENSION", 2)
    sur = s.sedes.crear("Sur", "Av. 3", None, None, None, "MONETARIA", 50)
    ana = s.socios.crear("30111222", "Ana", "Pérez", norte.id)
    luis = s.socios.crear("30111333", "Luis", "Gómez", centro.id)
    libro = s.catalogo.crear_libro("9789500000017", "Rayuela", "Cortázar")
    e_centro = s.catalogo.agregar_ejemplar(libro.id, centro.id)
    e_norte = s.catalogo.agregar_ejemplar(libro.id, norte.id)
    return dict(centro=centro, norte=norte, sur=sur, ana=ana, luis=luis, libro=libro,
                e_centro=e_centro, e_norte=e_norte)
