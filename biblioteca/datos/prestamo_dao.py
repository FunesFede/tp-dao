from __future__ import annotations

import sqlite3
from datetime import date

from ..modelo import Devolucion, Prestamo
from .conversiones import (fecha_a_texto, fecha_hora_a_texto, texto_a_fecha, texto_a_fecha_hora)


class PrestamoDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, p: Prestamo) -> int:
        cur = self.cx.execute("""
            INSERT INTO prestamo (socio_id, ejemplar_id, tipo, sede_origen_id, sede_destino_id,
                                  fecha_solicitud, fecha_inicio, fecha_vencimiento, fecha_devolucion, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self._valores(p))
        p.id = cur.lastrowid
        return p.id

    def actualizar(self, p: Prestamo) -> int:
        cur = self.cx.execute("""
            UPDATE prestamo
            SET socio_id = ?, ejemplar_id = ?, tipo = ?, sede_origen_id = ?, sede_destino_id = ?,
                fecha_solicitud = ?, fecha_inicio = ?, fecha_vencimiento = ?, fecha_devolucion = ?,
                estado = ?
            WHERE id = ?
        """, self._valores(p) + (p.id,))
        return cur.rowcount

    def obtener_por_id(self, prestamo_id: int) -> Prestamo | None:
        fila = self.cx.execute("SELECT * FROM prestamo WHERE id = ?", (prestamo_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def listar_activos_vencidos(self, hoy: date) -> list[Prestamo]:
        filas = self.cx.execute("""
            SELECT * FROM prestamo
            WHERE estado = 'ACTIVO' AND fecha_vencimiento < ?
        """, (fecha_a_texto(hoy),)).fetchall()
        return [self._mapear(f) for f in filas]

    def listar_resumen(self, estados: tuple[str, ...] | None = None, texto: str = "",
                       socio_id: int | None = None, prestamo_id: int | None = None) -> list[dict]:
        """Préstamos con socio, libro y sedes. `socio_id` y `prestamo_id` limitan el listado."""
        patron = f"%{texto.strip()}%"
        filtro_estado = ""
        parametros: list = [patron, patron, patron, patron, socio_id, socio_id, prestamo_id, prestamo_id]
        if estados:
            # El f-string solo arma los signos "?"; los valores van siempre como parámetros
            filtro_estado = f"AND p.estado IN ({', '.join('?' for _ in estados)})"
            parametros.extend(estados)
        filas = self.cx.execute(f"""
            SELECT p.*, s.apellido || ', ' || s.nombre AS socio, s.dni,
                   l.titulo, e.codigo_inventario, e.estado_fisico AS estado_fisico_ejemplar,
                   so.nombre AS sede_origen, sd.nombre AS sede_destino
            FROM prestamo p
            JOIN socio s ON s.id = p.socio_id
            JOIN ejemplar e ON e.id = p.ejemplar_id
            JOIN libro l ON l.id = e.libro_id
            JOIN sede so ON so.id = p.sede_origen_id
            JOIN sede sd ON sd.id = p.sede_destino_id
            WHERE (s.apellido LIKE ? OR s.dni LIKE ? OR l.titulo LIKE ? OR e.codigo_inventario LIKE ?)
              AND (? IS NULL OR p.socio_id = ?)
              AND (? IS NULL OR p.id = ?)
              {filtro_estado}
            ORDER BY p.fecha_solicitud DESC
        """, parametros).fetchall()
        return [dict(f) for f in filas]

    def obtener_resumen(self, prestamo_id: int) -> dict | None:
        """Un préstamo con los mismos datos que listar_resumen."""
        filas = self.listar_resumen(prestamo_id=prestamo_id)
        return filas[0] if filas else None

    @staticmethod
    def _valores(p: Prestamo) -> tuple:
        return (p.socio_id, p.ejemplar_id, p.tipo, p.sede_origen_id, p.sede_destino_id,
                fecha_hora_a_texto(p.fecha_solicitud), fecha_hora_a_texto(p.fecha_inicio),
                fecha_a_texto(p.fecha_vencimiento), fecha_hora_a_texto(p.fecha_devolucion), p.estado)

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Prestamo:
        return Prestamo(socio_id=f["socio_id"], ejemplar_id=f["ejemplar_id"], tipo=f["tipo"],
                        sede_origen_id=f["sede_origen_id"], sede_destino_id=f["sede_destino_id"],
                        fecha_solicitud=texto_a_fecha_hora(f["fecha_solicitud"]), estado=f["estado"],
                        fecha_inicio=texto_a_fecha_hora(f["fecha_inicio"]),
                        fecha_vencimiento=texto_a_fecha(f["fecha_vencimiento"]),
                        fecha_devolucion=texto_a_fecha_hora(f["fecha_devolucion"]), id=f["id"])


class DevolucionDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, d: Devolucion) -> int:
        cur = self.cx.execute("""
            INSERT INTO devolucion (prestamo_id, fecha, sede_recepcion_id, estado_fisico, observaciones)
            VALUES (?, ?, ?, ?, ?)
        """, (d.prestamo_id, fecha_hora_a_texto(d.fecha), d.sede_recepcion_id, d.estado_fisico,
              d.observaciones))
        d.id = cur.lastrowid
        return d.id

    def obtener_resumen_por_prestamo(self, prestamo_id: int) -> dict | None:
        """La devolución del préstamo con el nombre de la sede donde se recibió."""
        f = self.cx.execute("""
            SELECT d.*, s.nombre AS sede_recepcion
            FROM devolucion d
            JOIN sede s ON s.id = d.sede_recepcion_id
            WHERE d.prestamo_id = ?
        """, (prestamo_id,)).fetchone()
        return dict(f) if f else None

    def obtener_por_prestamo(self, prestamo_id: int) -> Devolucion | None:
        f = self.cx.execute("SELECT * FROM devolucion WHERE prestamo_id = ?", (prestamo_id,)).fetchone()
        if not f:
            return None
        return Devolucion(prestamo_id=f["prestamo_id"], fecha=texto_a_fecha_hora(f["fecha"]),
                          sede_recepcion_id=f["sede_recepcion_id"], estado_fisico=f["estado_fisico"],
                          observaciones=f["observaciones"], id=f["id"])
