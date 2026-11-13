from __future__ import annotations

import sqlite3

from ..modelo import Sede
from .conversiones import fecha_a_texto, texto_a_fecha


class SedeDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, sede: Sede) -> int:
        cur = self.cx.execute("""
            INSERT INTO sede (nombre, direccion, telefono, email, horario, activa, fecha_baja,
                              politica_sancion, monto_por_dia, factor_suspension)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self._valores(sede))
        sede.id = cur.lastrowid
        return sede.id

    def actualizar(self, sede: Sede) -> int:
        cur = self.cx.execute("""
            UPDATE sede
            SET nombre = ?, direccion = ?, telefono = ?, email = ?, horario = ?, activa = ?,
                fecha_baja = ?, politica_sancion = ?, monto_por_dia = ?, factor_suspension = ?
            WHERE id = ?
        """, self._valores(sede) + (sede.id,))
        return cur.rowcount

    def obtener_por_id(self, sede_id: int) -> Sede | None:
        fila = self.cx.execute("SELECT * FROM sede WHERE id = ?", (sede_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def listar(self, solo_activas: bool = False) -> list[Sede]:
        filas = self.cx.execute("""
            SELECT * FROM sede
            WHERE activa = 1 OR ? = 0
            ORDER BY nombre
        """, (1 if solo_activas else 0,)).fetchall()
        return [self._mapear(f) for f in filas]

    def contar_remitos_en_curso(self, sede_id: int) -> int:
        fila = self.cx.execute("""
            SELECT COUNT(*) FROM remito
            WHERE (sede_origen_id = ? OR sede_destino_id = ?)
              AND estado IN ('EN_PREPARACION', 'DESPACHADO', 'EN_TRANSITO')
        """, (sede_id, sede_id)).fetchone()
        return fila[0]

    def contar_pendientes(self, sede_id: int) -> dict[str, int]:
        """Lo que impide dar de baja la sede: préstamos, reservas y ejemplares que todavía dependen de ella."""
        fila = self.cx.execute("""
            SELECT
                (SELECT COUNT(*) FROM prestamo
                 WHERE (sede_origen_id = ? OR sede_destino_id = ?)
                   AND estado IN ('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO', 'ACTIVO', 'VENCIDO'))
                    AS prestamos,
                (SELECT COUNT(*) FROM reserva
                 WHERE sede_retiro_id = ? AND estado IN ('PENDIENTE', 'ASIGNADA')) AS reservas,
                (SELECT COUNT(*) FROM ejemplar
                 WHERE sede_actual_id = ? AND sede_id <> ? AND estado NOT IN ('BAJA', 'EXTRAVIADO'))
                    AS ajenos,
                (SELECT COUNT(*) FROM ejemplar
                 WHERE sede_id = ? AND sede_actual_id <> ? AND estado NOT IN ('BAJA', 'EXTRAVIADO'))
                    AS propios_afuera
        """, (sede_id,) * 7).fetchone()
        return dict(fila)

    @staticmethod
    def _valores(s: Sede) -> tuple:
        return (s.nombre, s.direccion, s.telefono, s.email, s.horario, int(s.activa),
                fecha_a_texto(s.fecha_baja), s.politica_sancion, s.monto_por_dia, s.factor_suspension)

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Sede:
        return Sede(nombre=f["nombre"], direccion=f["direccion"], telefono=f["telefono"],
                    email=f["email"], horario=f["horario"], politica_sancion=f["politica_sancion"],
                    monto_por_dia=f["monto_por_dia"], factor_suspension=f["factor_suspension"],
                    activa=bool(f["activa"]), fecha_baja=texto_a_fecha(f["fecha_baja"]), id=f["id"])
