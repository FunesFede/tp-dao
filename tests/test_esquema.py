"""El esquema carga y las restricciones de la base rechazan los casos inválidos."""
import sqlite3

import pytest

from biblioteca.datos import conexion


def insertar_basicos(cx):
    cx.execute("INSERT INTO sede (nombre, direccion, monto_por_dia) VALUES ('C', 'x', 100)")
    cx.execute("INSERT INTO sede (nombre, direccion, politica_sancion, factor_suspension) VALUES ('N', 'y', 'SUSPENSION', 2)")
    cx.execute("INSERT INTO socio (dni, nombre, apellido, sede_id) VALUES ('30111222', 'A', 'B', 1)")
    cx.execute("INSERT INTO libro (isbn, titulo, autor) VALUES ('9789500000017', 'T', 'A')")
    cx.execute("INSERT INTO ejemplar (libro_id, sede_id, sede_actual_id, codigo_inventario) VALUES (1, 1, 1, 'E1')")
    cx.execute("""INSERT INTO prestamo (socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id, estado)
                  VALUES (1, 1, 'LOCAL', 1, 1, 'ACTIVO')""")


def test_el_esquema_crea_todas_las_tablas(cx):
    tablas = {f[0] for f in cx.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tablas == {"sede", "socio", "libro", "ejemplar", "prestamo", "reserva", "remito", "remito_detalle",
                      "remito_movimiento", "devolucion", "sancion"}


INVALIDOS = [
    ("sede monetaria sin monto", "INSERT INTO sede (nombre, direccion) VALUES ('Z', 'z')"),
    ("sede suspensión sin factor",
     "INSERT INTO sede (nombre, direccion, politica_sancion) VALUES ('Z', 'z', 'SUSPENSION')"),
    ("sede de baja sin fecha", "INSERT INTO sede (nombre, direccion, monto_por_dia, activa) VALUES ('Z', 'z', 1, 0)"),
    ("sede activa con fecha de baja",
     "INSERT INTO sede (nombre, direccion, monto_por_dia, fecha_baja) VALUES ('Z', 'z', 1, '2026-01-01')"),
    ("socio con DNI duplicado", "INSERT INTO socio (dni, nombre, apellido, sede_id) VALUES ('30111222', 'X', 'Y', 1)"),
    ("socio inhabilitado sin motivo",
     "INSERT INTO socio (dni, nombre, apellido, sede_id, inhabilitado_manual) VALUES ('1', 'X', 'Y', 1, 1)"),
    ("socio de una sede inexistente", "INSERT INTO socio (dni, nombre, apellido, sede_id) VALUES ('2', 'X', 'Y', 99)"),
    ("libro con ISBN duplicado", "INSERT INTO libro (isbn, titulo, autor) VALUES ('9789500000017', 'X', 'Y')"),
    ("ejemplar con código duplicado",
     "INSERT INTO ejemplar (libro_id, sede_id, sede_actual_id, codigo_inventario) VALUES (1, 1, 1, 'E1')"),
    ("préstamo local con sedes distintas",
     "INSERT INTO prestamo (socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id) VALUES (1, 1, 'LOCAL', 1, 2)"),
    ("préstamo inter con la misma sede",
     "INSERT INTO prestamo (socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id) VALUES (1, 1, 'INTER', 1, 1)"),
    ("segundo préstamo abierto del mismo ejemplar",
     "INSERT INTO prestamo (socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id) VALUES (1, 1, 'LOCAL', 1, 1)"),
    ("remito con origen igual a destino",
     "INSERT INTO remito (numero, sede_origen_id, sede_destino_id) VALUES ('R', 1, 1)"),
    ("sanción monetaria sin monto",
     "INSERT INTO sancion (prestamo_id, socio_id, tipo, motivo, pagada) VALUES (1, 1, 'MONETARIA', 'ATRASO', 0)"),
    ("sanción de suspensión con monto",
     """INSERT INTO sancion (prestamo_id, socio_id, tipo, motivo, monto, suspendido_hasta)
        VALUES (1, 1, 'SUSPENSION', 'ATRASO', 10, '2026-01-01')"""),
    ("estado de ejemplar desconocido", "UPDATE ejemplar SET estado = 'PERDIDO'"),
]


@pytest.mark.parametrize("caso, sql", INVALIDOS, ids=[c for c, _ in INVALIDOS])
def test_restricciones(cx, caso, sql):
    insertar_basicos(cx)
    with pytest.raises(sqlite3.IntegrityError):
        cx.execute(sql)


def test_reserva_vigente_duplicada(cx):
    insertar_basicos(cx)
    cx.execute("INSERT INTO reserva (socio_id, libro_id, sede_retiro_id) VALUES (1, 1, 1)")
    with pytest.raises(sqlite3.IntegrityError):
        cx.execute("INSERT INTO reserva (socio_id, libro_id, sede_retiro_id) VALUES (1, 1, 1)")
    cx.execute("UPDATE reserva SET estado = 'CANCELADA'")
    cx.execute("INSERT INTO reserva (socio_id, libro_id, sede_retiro_id) VALUES (1, 1, 1)")


def test_un_prestamo_cerrado_libera_el_ejemplar(cx):
    insertar_basicos(cx)
    cx.execute("UPDATE prestamo SET estado = 'DEVUELTO'")
    cx.execute("""INSERT INTO prestamo (socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id)
                  VALUES (1, 1, 'LOCAL', 1, 1)""")


def test_inicializar_base_es_idempotente(tmp_path):
    anterior = conexion.ruta_actual()
    try:
        conexion.configurar_ruta(tmp_path / "x.db")
        assert conexion.inicializar_base() is True
        assert conexion.inicializar_base() is False
        assert conexion.inicializar_base(reiniciar=True) is True
        cx = conexion.obtener_conexion()
        assert cx.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        cx.close()
    finally:
        conexion.configurar_ruta(anterior)
