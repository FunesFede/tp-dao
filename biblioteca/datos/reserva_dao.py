from __future__ import annotations

import sqlite3
from datetime import date

from ..modelo import Reserva
from .conversiones import fecha_a_texto, fecha_hora_a_texto, texto_a_fecha, texto_a_fecha_hora


class ReservaDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, r: Reserva) -> int:
        cur = self.cx.execute("""
            INSERT INTO reserva (socio_id, libro_id, sede_retiro_id, ejemplar_asignado_id,
                                 fecha_reserva, fecha_expiracion, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, self._valores(r))
        r.id = cur.lastrowid
        return r.id

    def actualizar(self, r: Reserva) -> int:
        cur = self.cx.execute("""
            UPDATE reserva
            SET socio_id = ?, libro_id = ?, sede_retiro_id = ?, ejemplar_asignado_id = ?,
                fecha_reserva = ?, fecha_expiracion = ?, estado = ?
            WHERE id = ?
        """, self._valores(r) + (r.id,))
        return cur.rowcount

    def obtener_por_id(self, reserva_id: int) -> Reserva | None:
        fila = self.cx.execute("SELECT * FROM reserva WHERE id = ?", (reserva_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def listar_pendientes(self, libro_id: int, sede_id: int) -> list[Reserva]:
        """Reservas en espera de un ejemplar, por orden de llegada."""
        filas = self.cx.execute("""
            SELECT * FROM reserva
            WHERE libro_id = ? AND sede_retiro_id = ? AND estado = 'PENDIENTE'
            ORDER BY fecha_reserva, id
        """, (libro_id, sede_id)).fetchall()
        return [self._mapear(f) for f in filas]

    def listar_asignadas_vencidas(self, hoy: date) -> list[Reserva]:
        filas = self.cx.execute("""
            SELECT * FROM reserva
            WHERE estado = 'ASIGNADA' AND fecha_expiracion < ?
        """, (fecha_a_texto(hoy),)).fetchall()
        return [self._mapear(f) for f in filas]

    def listar_resumen(self, solo_vigentes: bool = False, socio_id: int | None = None) -> list[dict]:
        """Reservas con socio, libro y sede. `socio_id` limita el listado a las de ese socio."""
        filas = self.cx.execute("""
            SELECT r.*, s.apellido || ', ' || s.nombre AS socio, s.dni, l.titulo,
                   se.nombre AS sede_retiro, e.codigo_inventario
            FROM reserva r
            JOIN socio s ON s.id = r.socio_id
            JOIN libro l ON l.id = r.libro_id
            JOIN sede se ON se.id = r.sede_retiro_id
            LEFT JOIN ejemplar e ON e.id = r.ejemplar_asignado_id
            WHERE (? = 0 OR r.estado IN ('PENDIENTE', 'ASIGNADA'))
              AND (? IS NULL OR r.socio_id = ?)
            ORDER BY r.fecha_reserva DESC
        """, (int(solo_vigentes), socio_id, socio_id)).fetchall()
        return [dict(f) for f in filas]

    @staticmethod
    def _valores(r: Reserva) -> tuple:
        return (r.socio_id, r.libro_id, r.sede_retiro_id, r.ejemplar_asignado_id,
                fecha_hora_a_texto(r.fecha_reserva), fecha_a_texto(r.fecha_expiracion), r.estado)

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Reserva:
        return Reserva(socio_id=f["socio_id"], libro_id=f["libro_id"], sede_retiro_id=f["sede_retiro_id"],
                       fecha_reserva=texto_a_fecha_hora(f["fecha_reserva"]), estado=f["estado"],
                       ejemplar_asignado_id=f["ejemplar_asignado_id"],
                       fecha_expiracion=texto_a_fecha(f["fecha_expiracion"]), id=f["id"])
