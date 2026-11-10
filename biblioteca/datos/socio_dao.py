from __future__ import annotations

import sqlite3

from ..modelo import Socio
from .conversiones import fecha_a_texto, texto_a_fecha


class SocioDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, socio: Socio) -> int:
        cur = self.cx.execute("""
            INSERT INTO socio (dni, nombre, apellido, email, telefono, sede_id, suspendido_hasta,
                               inhabilitado_manual, motivo_inhabilitacion, fecha_alta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self._valores(socio))
        socio.id = cur.lastrowid
        return socio.id

    def actualizar(self, socio: Socio) -> int:
        cur = self.cx.execute("""
            UPDATE socio
            SET dni = ?, nombre = ?, apellido = ?, email = ?, telefono = ?, sede_id = ?,
                suspendido_hasta = ?, inhabilitado_manual = ?, motivo_inhabilitacion = ?, fecha_alta = ?
            WHERE id = ?
        """, self._valores(socio) + (socio.id,))
        return cur.rowcount

    def obtener_por_id(self, socio_id: int) -> Socio | None:
        fila = self.cx.execute("SELECT * FROM socio WHERE id = ?", (socio_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def obtener_por_dni(self, dni: str) -> Socio | None:
        fila = self.cx.execute("SELECT * FROM socio WHERE dni = ?", (dni,)).fetchone()
        return self._mapear(fila) if fila else None

    def listar_resumen(self, texto: str = "") -> list[dict]:
        """Socios con su sede, préstamos abiertos y multas impagas, para mostrar en pantalla."""
        patron = f"%{texto.strip()}%"
        filas = self.cx.execute("""
            SELECT s.*, se.nombre AS sede,
                   (SELECT COUNT(*) FROM prestamo p
                     WHERE p.socio_id = s.id
                       AND p.estado IN ('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO',
                                        'ACTIVO', 'VENCIDO')) AS prestamos_abiertos,
                   (SELECT COALESCE(SUM(monto), 0) FROM sancion sa
                     WHERE sa.socio_id = s.id AND sa.tipo = 'MONETARIA' AND sa.pagada = 0) AS deuda
            FROM socio s
            JOIN sede se ON se.id = s.sede_id
            WHERE s.dni LIKE ? OR s.apellido LIKE ? OR s.nombre LIKE ?
            ORDER BY s.apellido, s.nombre
        """, (patron, patron, patron)).fetchall()
        return [dict(f) | {"socio": self._mapear(f)} for f in filas]

    def contar_prestamos_abiertos(self, socio_id: int) -> int:
        fila = self.cx.execute("""
            SELECT COUNT(*) FROM prestamo
            WHERE socio_id = ?
              AND estado IN ('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO', 'ACTIVO', 'VENCIDO')
        """, (socio_id,)).fetchone()
        return fila[0]

    @staticmethod
    def _valores(s: Socio) -> tuple:
        return (s.dni, s.nombre, s.apellido, s.email, s.telefono, s.sede_id,
                fecha_a_texto(s.suspendido_hasta), int(s.inhabilitado_manual),
                s.motivo_inhabilitacion, fecha_a_texto(s.fecha_alta))

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Socio:
        return Socio(dni=f["dni"], nombre=f["nombre"], apellido=f["apellido"], sede_id=f["sede_id"],
                     email=f["email"], telefono=f["telefono"],
                     suspendido_hasta=texto_a_fecha(f["suspendido_hasta"]),
                     inhabilitado_manual=bool(f["inhabilitado_manual"]),
                     motivo_inhabilitacion=f["motivo_inhabilitacion"],
                     fecha_alta=texto_a_fecha(f["fecha_alta"]), id=f["id"])
