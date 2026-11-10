from __future__ import annotations

import sqlite3

from ..modelo import Multa, Sancion, Suspension, TipoSancion
from .conversiones import fecha_a_texto, fecha_hora_a_texto, texto_a_fecha, texto_a_fecha_hora


class SancionDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, s: Sancion) -> int:
        es_multa = isinstance(s, Multa)
        cur = self.cx.execute("""
            INSERT INTO sancion (prestamo_id, socio_id, tipo, motivo, dias_atraso, monto, pagada,
                                 suspendido_hasta, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (s.prestamo_id, s.socio_id, s.tipo, s.motivo, s.dias_atraso,
              s.monto if es_multa else None,
              int(s.pagada) if es_multa else None,
              None if es_multa else fecha_a_texto(s.suspendido_hasta),
              fecha_hora_a_texto(s.fecha)))
        s.id = cur.lastrowid
        return s.id

    def marcar_pagada(self, multa: Multa) -> int:
        cur = self.cx.execute("UPDATE sancion SET pagada = ? WHERE id = ? AND tipo = 'MONETARIA'",
                              (int(multa.pagada), multa.id))
        return cur.rowcount

    def obtener_por_id(self, sancion_id: int) -> Sancion | None:
        fila = self.cx.execute("SELECT * FROM sancion WHERE id = ?", (sancion_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def listar_resumen(self, socio_id: int | None = None) -> list[dict]:
        filas = self.cx.execute("""
            SELECT sa.*, s.apellido || ', ' || s.nombre AS socio, l.titulo
            FROM sancion sa
            JOIN socio s ON s.id = sa.socio_id
            JOIN prestamo p ON p.id = sa.prestamo_id
            JOIN ejemplar e ON e.id = p.ejemplar_id
            JOIN libro l ON l.id = e.libro_id
            WHERE ? IS NULL OR sa.socio_id = ?
            ORDER BY sa.fecha DESC
        """, (socio_id, socio_id)).fetchall()
        return [dict(f) for f in filas]

    def listar_por_prestamo(self, prestamo_id: int) -> list[Sancion]:
        filas = self.cx.execute("SELECT * FROM sancion WHERE prestamo_id = ? ORDER BY fecha, id",
                                (prestamo_id,)).fetchall()
        return [self._mapear(f) for f in filas]

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Sancion:
        comunes = dict(prestamo_id=f["prestamo_id"], socio_id=f["socio_id"], dias_atraso=f["dias_atraso"],
                       fecha=texto_a_fecha_hora(f["fecha"]), motivo=f["motivo"], id=f["id"])
        if f["tipo"] == TipoSancion.MONETARIA:
            return Multa(**comunes, monto=f["monto"], pagada=bool(f["pagada"]))
        return Suspension(**comunes, suspendido_hasta=texto_a_fecha(f["suspendido_hasta"]))
