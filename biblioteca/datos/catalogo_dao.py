from __future__ import annotations

import sqlite3

from ..modelo import Ejemplar, Libro


class LibroDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, libro: Libro) -> int:
        cur = self.cx.execute("""
            INSERT INTO libro (isbn, titulo, autor, editorial, anio, tipo_material)
            VALUES (?, ?, ?, ?, ?, ?)
        """, self._valores(libro))
        libro.id = cur.lastrowid
        return libro.id

    def actualizar(self, libro: Libro) -> int:
        cur = self.cx.execute("""
            UPDATE libro
            SET isbn = ?, titulo = ?, autor = ?, editorial = ?, anio = ?, tipo_material = ?
            WHERE id = ?
        """, self._valores(libro) + (libro.id,))
        return cur.rowcount

    def obtener_por_id(self, libro_id: int) -> Libro | None:
        fila = self.cx.execute("SELECT * FROM libro WHERE id = ?", (libro_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def listar_resumen(self, texto: str = "") -> list[dict]:
        """Libros con la cantidad de ejemplares totales (incluidas las bajas), disponibles y dados de baja.

        Los ejemplares de una sede dada de baja no cuentan como disponibles: no se pueden prestar.
        """
        patron = f"%{texto.strip()}%"
        filas = self.cx.execute("""
            SELECT l.*,
                   COUNT(e.id) AS ejemplares,
                   COALESCE(SUM(e.estado = 'DISPONIBLE' AND s.activa = 1), 0) AS disponibles,
                   COALESCE(SUM(e.estado = 'BAJA'), 0) AS bajas
            FROM libro l
            LEFT JOIN ejemplar e ON e.libro_id = l.id
            LEFT JOIN sede s ON s.id = e.sede_id
            WHERE l.titulo LIKE ? OR l.autor LIKE ? OR l.isbn LIKE ?
            GROUP BY l.id
            ORDER BY l.titulo
        """, (patron, patron, patron)).fetchall()
        return [dict(f) | {"libro": self._mapear(f)} for f in filas]

    @staticmethod
    def _valores(l: Libro) -> tuple:
        return (l.isbn, l.titulo, l.autor, l.editorial, l.anio, l.tipo_material)

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Libro:
        return Libro(isbn=f["isbn"], titulo=f["titulo"], autor=f["autor"], editorial=f["editorial"],
                     anio=f["anio"], tipo_material=f["tipo_material"], id=f["id"])


class EjemplarDAO:
    def __init__(self, conexion: sqlite3.Connection):
        self.cx = conexion

    def crear(self, ejemplar: Ejemplar) -> int:
        cur = self.cx.execute("""
            INSERT INTO ejemplar (libro_id, sede_id, sede_actual_id, codigo_inventario, estado, estado_fisico)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ejemplar.libro_id, ejemplar.sede_id, ejemplar.sede_actual_id,
              ejemplar.codigo_inventario, ejemplar.estado, ejemplar.estado_fisico))
        ejemplar.id = cur.lastrowid
        return ejemplar.id

    def actualizar(self, ejemplar: Ejemplar) -> int:
        cur = self.cx.execute("""
            UPDATE ejemplar
            SET sede_actual_id = ?, estado = ?, estado_fisico = ?
            WHERE id = ?
        """, (ejemplar.sede_actual_id, ejemplar.estado, ejemplar.estado_fisico, ejemplar.id))
        return cur.rowcount

    def obtener_por_id(self, ejemplar_id: int) -> Ejemplar | None:
        fila = self.cx.execute("SELECT * FROM ejemplar WHERE id = ?", (ejemplar_id,)).fetchone()
        return self._mapear(fila) if fila else None

    def siguiente_numero(self, libro_id: int, sede_id: int) -> int:
        fila = self.cx.execute("""
            SELECT COUNT(*) FROM ejemplar WHERE libro_id = ? AND sede_id = ?
        """, (libro_id, sede_id)).fetchone()
        return fila[0] + 1

    def listar_disponibles_en_su_sede(self, libro_id: int, sede_id: int) -> list[Ejemplar]:
        """Ejemplares de la sede, físicamente en ella y disponibles (si la sede está activa)."""
        filas = self.cx.execute("""
            SELECT e.* FROM ejemplar e
            JOIN sede s ON s.id = e.sede_id
            WHERE e.libro_id = ? AND e.sede_id = ? AND e.sede_actual_id = ? AND e.estado = 'DISPONIBLE'
              AND s.activa = 1
            ORDER BY e.codigo_inventario
        """, (libro_id, sede_id, sede_id)).fetchall()
        return [self._mapear(f) for f in filas]

    def contar_de_sede(self, libro_id: int, sede_id: int) -> int:
        fila = self.cx.execute("""
            SELECT COUNT(*) FROM ejemplar
            WHERE libro_id = ? AND sede_id = ? AND estado NOT IN ('BAJA', 'EXTRAVIADO')
        """, (libro_id, sede_id)).fetchone()
        return fila[0]

    def listar_resumen(self, libro_id: int | None = None, sede_id: int | None = None,
                       solo_prestables: bool = False) -> list[dict]:
        """Ejemplares con título y nombres de sedes.

        `solo_prestables`: disponibles, en su sede y con la sede propietaria activa.
        """
        filas = self.cx.execute("""
            SELECT e.*, l.titulo, l.autor, sp.nombre AS sede, sp.activa AS sede_activa,
                   sa.nombre AS sede_actual,
                   -- Para qué está apartado un ejemplar RESERVADO: un préstamo sin entregar o una reserva
                   (SELECT p.id FROM prestamo p
                    WHERE p.ejemplar_id = e.id
                      AND p.estado IN ('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO')) AS apartado_prestamo_id,
                   (SELECT so.apellido FROM reserva r JOIN socio so ON so.id = r.socio_id
                    WHERE r.ejemplar_asignado_id = e.id AND r.estado = 'ASIGNADA') AS apartado_reserva_de
            FROM ejemplar e
            JOIN libro l ON l.id = e.libro_id
            JOIN sede sp ON sp.id = e.sede_id
            JOIN sede sa ON sa.id = e.sede_actual_id
            WHERE (? IS NULL OR e.libro_id = ?)
              AND (? IS NULL OR e.sede_id = ?)
              AND (? = 0 OR (e.estado = 'DISPONIBLE' AND e.sede_actual_id = e.sede_id AND sp.activa = 1))
            ORDER BY l.titulo, e.codigo_inventario
        """, (libro_id, libro_id, sede_id, sede_id, int(solo_prestables))).fetchall()
        return [dict(f) for f in filas]

    def libros_de_sede(self, sede_id: int) -> list[dict]:
        """Libros con ejemplares propios de la sede (sin bajas ni extraviados) y cuántos están disponibles."""
        filas = self.cx.execute("""
            SELECT l.id, l.titulo, l.autor,
                   COUNT(*) AS ejemplares,
                   SUM(e.estado = 'DISPONIBLE' AND e.sede_actual_id = e.sede_id) AS disponibles
            FROM ejemplar e
            JOIN libro l ON l.id = e.libro_id
            WHERE e.sede_id = ? AND e.estado NOT IN ('BAJA', 'EXTRAVIADO')
            GROUP BY l.id
            ORDER BY l.titulo
        """, (sede_id,)).fetchall()
        return [dict(f) for f in filas]

    def disponibilidad_por_sede(self, libro_id: int) -> list[dict]:
        filas = self.cx.execute("""
            SELECT s.id AS sede_id, s.nombre AS sede, s.activa,
                   COUNT(e.id) AS total,
                   COALESCE(SUM(e.estado = 'DISPONIBLE' AND e.sede_actual_id = e.sede_id
                                AND s.activa = 1), 0) AS disponibles,
                   COALESCE(SUM(e.estado = 'PRESTADO'), 0) AS prestados,
                   COALESCE(SUM(e.estado = 'RESERVADO' AND e.sede_actual_id = e.sede_id), 0) AS reservados,
                   COALESCE(SUM(e.estado = 'EN_TRANSITO'
                                OR (e.sede_actual_id <> e.sede_id
                                    AND e.estado IN ('DISPONIBLE', 'RESERVADO'))), 0) AS fuera_de_sede
            FROM sede s
            LEFT JOIN ejemplar e ON e.sede_id = s.id AND e.libro_id = ?
                                 AND e.estado NOT IN ('BAJA', 'EXTRAVIADO')
            GROUP BY s.id
            ORDER BY s.nombre
        """, (libro_id,)).fetchall()
        return [dict(f) for f in filas]

    @staticmethod
    def _mapear(f: sqlite3.Row) -> Ejemplar:
        return Ejemplar(libro_id=f["libro_id"], sede_id=f["sede_id"], sede_actual_id=f["sede_actual_id"],
                        codigo_inventario=f["codigo_inventario"], estado=f["estado"],
                        estado_fisico=f["estado_fisico"], id=f["id"])
