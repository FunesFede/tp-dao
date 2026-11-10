"""DAO del remito.

El remito se carga y se guarda completo (cabecera, detalle e historial), porque es un agregado:
sus ejemplares y movimientos no tienen sentido por separado. Al cargar, el texto del estado se
convierte en el objeto State con Remito.estado_desde_codigo().
"""
from __future__ import annotations

import sqlite3

from ..modelo import Movimiento, Remito
from .conversiones import fecha_hora_a_texto, texto_a_fecha_hora


class RemitoDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def siguiente_numero(self) -> str:
        fila = self.cx.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM remito").fetchone()
        return f"R-{fila[0]:05d}"

    def crear(self, remito: Remito) -> int:
        cur = self.cx.execute("""
            INSERT INTO remito (numero, sede_origen_id, sede_destino_id, estado, fecha_creacion)
            VALUES (?, ?, ?, ?, ?)
        """, (remito.numero, remito.sede_origen_id, remito.sede_destino_id, remito.estado,
              fecha_hora_a_texto(remito.fecha_creacion)))
        remito.id = cur.lastrowid
        self._guardar_detalle(remito)
        self._guardar_movimientos_nuevos(remito)
        return remito.id

    def guardar(self, remito: Remito) -> None:
        self.cx.execute("UPDATE remito SET estado = ? WHERE id = ?", (remito.estado, remito.id))
        self._guardar_detalle(remito)
        self._guardar_movimientos_nuevos(remito)

    def obtener_por_id(self, remito_id: int) -> Remito | None:
        fila = self.cx.execute("SELECT * FROM remito WHERE id = ?", (remito_id,)).fetchone()
        if fila is None:
            return None
        detalle = self.cx.execute("""
            SELECT ejemplar_id, prestamo_id, estado_recepcion
            FROM remito_detalle
            WHERE remito_id = ?
        """, (remito_id,)).fetchall()
        movimientos = self.cx.execute("""
            SELECT * FROM remito_movimiento
            WHERE remito_id = ?
            ORDER BY fecha_hora, id
        """, (remito_id,)).fetchall()
        return Remito(
            id=fila["id"],
            numero=fila["numero"],
            sede_origen_id=fila["sede_origen_id"],
            sede_destino_id=fila["sede_destino_id"],
            estado=Remito.estado_desde_codigo(fila["estado"]),
            ejemplares={d["ejemplar_id"]: d["prestamo_id"] for d in detalle},
            recepcion={d["ejemplar_id"]: d["estado_recepcion"] for d in detalle if d["estado_recepcion"]},
            historial=[Movimiento(m["estado_anterior"], m["estado_nuevo"],
                                  texto_a_fecha_hora(m["fecha_hora"]), m["sede_id"], m["observacion"] or "")
                       for m in movimientos],
            fecha_creacion=texto_a_fecha_hora(fila["fecha_creacion"]),
        )

    def obtener_en_preparacion(self, sede_origen_id: int, sede_destino_id: int) -> Remito | None:
        fila = self.cx.execute("""
            SELECT id FROM remito
            WHERE sede_origen_id = ? AND sede_destino_id = ? AND estado = 'EN_PREPARACION'
            ORDER BY id LIMIT 1
        """, (sede_origen_id, sede_destino_id)).fetchone()
        return self.obtener_por_id(fila["id"]) if fila else None

    def obtener_en_curso_por_ejemplar(self, ejemplar_id: int) -> Remito | None:
        fila = self.cx.execute("""
            SELECT r.id FROM remito r
            JOIN remito_detalle d ON d.remito_id = r.id
            WHERE d.ejemplar_id = ? AND r.estado IN ('EN_PREPARACION', 'DESPACHADO', 'EN_TRANSITO')
        """, (ejemplar_id,)).fetchone()
        return self.obtener_por_id(fila["id"]) if fila else None

    def listar_resumen(self, solo_en_curso: bool = False) -> list[dict]:
        filas = self.cx.execute("""
            SELECT r.*, so.nombre AS sede_origen, sd.nombre AS sede_destino,
                   (SELECT COUNT(*) FROM remito_detalle d WHERE d.remito_id = r.id) AS ejemplares,
                   (SELECT MAX(fecha_hora) FROM remito_movimiento m WHERE m.remito_id = r.id) AS ultimo_movimiento
            FROM remito r
            JOIN sede so ON so.id = r.sede_origen_id
            JOIN sede sd ON sd.id = r.sede_destino_id
            WHERE ? = 0 OR r.estado IN ('EN_PREPARACION', 'DESPACHADO', 'EN_TRANSITO')
            ORDER BY r.id DESC
        """, (int(solo_en_curso),)).fetchall()
        return [dict(f) for f in filas]

    def listar_detalle(self, remito_id: int) -> list[dict]:
        filas = self.cx.execute("""
            SELECT d.*, e.codigo_inventario, e.estado AS estado_ejemplar, l.titulo,
                   s.apellido || ', ' || s.nombre AS socio
            FROM remito_detalle d
            JOIN ejemplar e ON e.id = d.ejemplar_id
            JOIN libro l ON l.id = e.libro_id
            LEFT JOIN prestamo p ON p.id = d.prestamo_id
            LEFT JOIN socio s ON s.id = p.socio_id
            WHERE d.remito_id = ?
            ORDER BY l.titulo
        """, (remito_id,)).fetchall()
        return [dict(f) for f in filas]

    def listar_movimientos(self, remito_id: int) -> list[dict]:
        filas = self.cx.execute("""
            SELECT m.*, s.nombre AS sede
            FROM remito_movimiento m
            LEFT JOIN sede s ON s.id = m.sede_id
            WHERE m.remito_id = ?
            ORDER BY m.fecha_hora, m.id
        """, (remito_id,)).fetchall()
        return [dict(f) for f in filas]

    # --- internos ------------------------------------------------------------
    def _guardar_detalle(self, remito: Remito) -> None:
        self.cx.execute("DELETE FROM remito_detalle WHERE remito_id = ?", (remito.id,))
        self.cx.executemany("""
            INSERT INTO remito_detalle (remito_id, ejemplar_id, prestamo_id, estado_recepcion)
            VALUES (?, ?, ?, ?)
        """, [(remito.id, e, p, remito.recepcion.get(e)) for e, p in remito.ejemplares.items()])

    def _guardar_movimientos_nuevos(self, remito: Remito) -> None:
        guardados = self.cx.execute("""
            SELECT COUNT(*) FROM remito_movimiento WHERE remito_id = ?
        """, (remito.id,)).fetchone()[0]
        self.cx.executemany("""
            INSERT INTO remito_movimiento (remito_id, estado_anterior, estado_nuevo, fecha_hora, sede_id, observacion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(remito.id, m.estado_anterior, m.estado_nuevo, fecha_hora_a_texto(m.fecha_hora),
               m.sede_id, m.observacion) for m in remito.historial[guardados:]])
