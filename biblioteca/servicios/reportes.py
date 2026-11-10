"""Reportes de gestión. SQL con agregaciones y joins; devuelve objetos Reporte."""
from __future__ import annotations

from ..datos.conversiones import fecha_a_texto
from ..reportes.estructura import Grafico, Reporte
from .base import ServicioBase

ABIERTOS = "('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO', 'ACTIVO', 'VENCIDO')"


class ServicioReportes(ServicioBase):
    CATALOGO = {
        "prestamos_activos": "Préstamos abiertos y material en tránsito",
        "vencidos_sanciones": "Préstamos vencidos y sanciones por socio",
        "mas_solicitados": "Libros más solicitados entre sedes",
        "disponibilidad": "Disponibilidad del catálogo por sede",
        "envios": "Tasa de envíos exitosos e incidencias",
        "transito": "Tiempo promedio de tránsito entre sedes",
    }

    def generar(self, clave: str) -> Reporte:
        metodo = getattr(self, f"_reporte_{clave}", None)
        if metodo is None:
            raise ValueError(f"Reporte desconocido: {clave}")
        with self._transaccion() as r:
            return metodo(r.conexion)

    def _nuevo(self, clave: str, descripcion: str, columnas: list[str], filas) -> Reporte:
        return Reporte(clave=clave, titulo=self.CATALOGO[clave], descripcion=descripcion,
                       columnas=columnas, filas=[list(f) for f in filas], generado=self.ahora())

    # -----------------------------------------------------------------------
    def _reporte_prestamos_activos(self, cx) -> Reporte:
        filas = cx.execute(f"""
            SELECT CASE p.estado
                       WHEN 'ACTIVO' THEN 'En poder del socio'
                       WHEN 'VENCIDO' THEN 'Vencido'
                       WHEN 'LISTO_PARA_RETIRO' THEN 'Listo para retirar'
                       ELSE 'Esperando envío'
                   END AS situacion,
                   l.titulo, e.codigo_inventario, s.apellido || ', ' || s.nombre AS socio,
                   CASE WHEN p.tipo = 'LOCAL' THEN so.nombre || ' (local)'
                        ELSE so.nombre || ' → ' || sd.nombre END AS recorrido,
                   COALESCE(p.fecha_inicio, p.fecha_solicitud) AS desde, p.fecha_vencimiento
            FROM prestamo p
            JOIN socio s ON s.id = p.socio_id
            JOIN ejemplar e ON e.id = p.ejemplar_id
            JOIN libro l ON l.id = e.libro_id
            JOIN sede so ON so.id = p.sede_origen_id
            JOIN sede sd ON sd.id = p.sede_destino_id
            WHERE p.estado IN {ABIERTOS} AND p.estado <> 'EN_TRANSITO'

            UNION ALL

            SELECT 'En tránsito (' || r.numero || ')', l.titulo, e.codigo_inventario,
                   COALESCE(s.apellido || ', ' || s.nombre, 'Retorno a su sede'),
                   so.nombre || ' → ' || sd.nombre,
                   (SELECT MIN(m.fecha_hora) FROM remito_movimiento m
                     WHERE m.remito_id = r.id AND m.estado_nuevo = 'DESPACHADO'),
                   p.fecha_vencimiento
            FROM remito r
            JOIN remito_detalle d ON d.remito_id = r.id
            JOIN ejemplar e ON e.id = d.ejemplar_id
            JOIN libro l ON l.id = e.libro_id
            JOIN sede so ON so.id = r.sede_origen_id
            JOIN sede sd ON sd.id = r.sede_destino_id
            LEFT JOIN prestamo p ON p.id = d.prestamo_id
            LEFT JOIN socio s ON s.id = p.socio_id
            WHERE r.estado IN ('DESPACHADO', 'EN_TRANSITO')
            ORDER BY 1, 6
        """).fetchall()
        reporte = self._nuevo("prestamos_activos",
                              "Préstamos que no se cerraron y ejemplares que están viajando entre sedes.",
                              ["Situación", "Libro", "Código", "Socio", "Recorrido", "Desde", "Vence"], filas)
        conteo: dict[str, int] = {}
        for fila in reporte.filas:
            clave = "En tránsito" if fila[0].startswith("En tránsito") else fila[0]
            conteo[clave] = conteo.get(clave, 0) + 1
        if conteo:
            reporte.grafico = Grafico("barras", "Ejemplares por situación", list(conteo), list(conteo.values()),
                                      "Ejemplares")
        reporte.totales = [f"Total: {len(reporte.filas)}"] + [""] * (len(reporte.columnas) - 1)
        return reporte

    def _reporte_vencidos_sanciones(self, cx) -> Reporte:
        hoy = fecha_a_texto(self.ahora().date())
        filas = cx.execute("""
            SELECT s.apellido || ', ' || s.nombre AS socio, s.dni,
                   (SELECT COUNT(*) FROM prestamo p
                     WHERE p.socio_id = s.id AND p.estado IN ('ACTIVO', 'VENCIDO')
                       AND p.fecha_vencimiento < :hoy) AS vencidos,
                   (SELECT CAST(MAX(julianday(:hoy) - julianday(p.fecha_vencimiento)) AS INTEGER)
                      FROM prestamo p
                     WHERE p.socio_id = s.id AND p.estado IN ('ACTIVO', 'VENCIDO')
                       AND p.fecha_vencimiento < :hoy) AS max_atraso,
                   COALESCE(SUM(sa.tipo = 'MONETARIA'), 0) AS multas,
                   COALESCE(SUM(CASE WHEN sa.tipo = 'MONETARIA' THEN sa.monto END), 0.0) AS total_multas,
                   COALESCE(SUM(CASE WHEN sa.tipo = 'MONETARIA' AND sa.pagada = 0 THEN sa.monto END), 0.0) AS impago,
                   COALESCE(SUM(sa.tipo = 'SUSPENSION'), 0) AS suspensiones,
                   CASE WHEN s.suspendido_hasta > :hoy THEN s.suspendido_hasta END AS suspendido_hasta
            FROM socio s
            LEFT JOIN sancion sa ON sa.socio_id = s.id
            GROUP BY s.id
            HAVING vencidos > 0 OR multas > 0 OR suspensiones > 0
            ORDER BY impago DESC, vencidos DESC, socio
        """, {"hoy": hoy}).fetchall()
        reporte = self._nuevo("vencidos_sanciones",
                              "Socios con préstamos vencidos sin devolver o con sanciones registradas.",
                              ["Socio", "DNI", "Vencidos", "Máx. atraso (días)", "Multas", "Total multas $",
                               "Impago $", "Suspensiones", "Suspendido hasta"], filas)
        con_deuda = [f for f in reporte.filas if f[6] > 0][:10]
        if con_deuda:
            reporte.grafico = Grafico("barras_h", "Multas impagas por socio", [f[0] for f in con_deuda],
                                      [f[6] for f in con_deuda], "Pesos")
        reporte.totales = ["Total", "", sum(f[2] for f in reporte.filas), "", sum(f[4] for f in reporte.filas),
                           sum(f[5] for f in reporte.filas), sum(f[6] for f in reporte.filas),
                           sum(f[7] for f in reporte.filas), ""]
        return reporte

    def _reporte_mas_solicitados(self, cx) -> Reporte:
        filas = cx.execute("""
            SELECT l.titulo, l.autor, COUNT(*) AS solicitudes,
                   COUNT(DISTINCT p.sede_destino_id) AS sedes_destino,
                   COUNT(DISTINCT p.socio_id) AS socios,
                   SUM(p.estado = 'CANCELADO') AS canceladas
            FROM prestamo p
            JOIN ejemplar e ON e.id = p.ejemplar_id
            JOIN libro l ON l.id = e.libro_id
            WHERE p.tipo = 'INTER'
            GROUP BY l.id
            ORDER BY solicitudes DESC, l.titulo
            LIMIT 10
        """).fetchall()
        reporte = self._nuevo("mas_solicitados",
                              "Los diez títulos con más préstamos interbibliotecarios solicitados.",
                              ["Libro", "Autor", "Solicitudes", "Sedes que lo pidieron", "Socios", "Canceladas"],
                              filas)
        if reporte.filas:
            reporte.grafico = Grafico("barras_h", "Solicitudes interbibliotecarias por título",
                                      [f[0] for f in reporte.filas], [f[2] for f in reporte.filas], "Solicitudes")
        return reporte

    def _reporte_disponibilidad(self, cx) -> Reporte:
        filas = cx.execute("""
            SELECT s.nombre || CASE WHEN s.activa = 0 THEN ' (baja)' ELSE '' END AS sede,
                   COUNT(DISTINCT CASE WHEN e.estado NOT IN ('BAJA', 'EXTRAVIADO') THEN e.libro_id END) AS titulos,
                   COALESCE(SUM(e.estado NOT IN ('BAJA', 'EXTRAVIADO')), 0) AS ejemplares,
                   COALESCE(SUM(e.estado = 'DISPONIBLE' AND e.sede_actual_id = e.sede_id), 0) AS disponibles,
                   COALESCE(SUM(e.estado = 'PRESTADO'), 0) AS prestados,
                   COALESCE(SUM(e.estado = 'RESERVADO' AND e.sede_actual_id = e.sede_id), 0) AS reservados,
                   COALESCE(SUM(e.estado = 'EN_TRANSITO'
                                OR (e.sede_actual_id <> e.sede_id
                                    AND e.estado IN ('DISPONIBLE', 'RESERVADO'))), 0) AS fuera,
                   COALESCE(SUM(e.estado = 'EXTRAVIADO'), 0) AS extraviados,
                   COALESCE(SUM(e.estado = 'BAJA'), 0) AS bajas
            FROM sede s
            LEFT JOIN ejemplar e ON e.sede_id = s.id
            GROUP BY s.id
            ORDER BY s.activa DESC, s.nombre
        """).fetchall()
        reporte = self._nuevo("disponibilidad",
                              "Ejemplares propios de cada sede según su estado. «Disponibles» y «Apartados» "
                              "están en su sede; «Fuera de su sede» incluye los que viajan y los que esperan "
                              "volver. Cada ejemplar cuenta en una sola columna.",
                              ["Sede", "Títulos", "Ejemplares", "Disponibles", "Prestados", "Apartados",
                               "Fuera de su sede", "Extraviados", "Bajas"], filas)
        reporte.grafico = Grafico("barras", "Ejemplares disponibles por sede", [f[0] for f in reporte.filas],
                                  [f[3] for f in reporte.filas], "Ejemplares")
        reporte.totales = ["Total"] + [sum(f[i] for f in reporte.filas) for i in range(1, 9)]
        reporte.totales[1] = cx.execute(
            "SELECT COUNT(DISTINCT libro_id) FROM ejemplar WHERE estado NOT IN ('BAJA', 'EXTRAVIADO')").fetchone()[0]
        return reporte

    def _reporte_envios(self, cx) -> Reporte:
        filas = cx.execute("""
            SELECT so.nombre || ' → ' || sd.nombre AS ruta,
                   COUNT(*) AS envios,
                   SUM(r.estado = 'RECIBIDO') AS exitosos,
                   SUM(r.estado = 'RECIBIDO_CON_INCIDENCIA') AS con_incidencia,
                   SUM(r.estado = 'EXTRAVIADO') AS extraviados,
                   (SELECT COUNT(*) FROM remito_detalle d JOIN remito r2 ON r2.id = d.remito_id
                     WHERE r2.sede_origen_id = r.sede_origen_id AND r2.sede_destino_id = r.sede_destino_id
                       AND d.estado_recepcion IN ('DANIADO', 'FALTANTE', 'DESTRUIDO')) AS ejemplares_afectados,
                   ROUND(100.0 * SUM(r.estado = 'RECIBIDO') / COUNT(*), 1) AS tasa
            FROM remito r
            JOIN sede so ON so.id = r.sede_origen_id
            JOIN sede sd ON sd.id = r.sede_destino_id
            WHERE r.estado IN ('RECIBIDO', 'RECIBIDO_CON_INCIDENCIA', 'EXTRAVIADO')
            GROUP BY r.sede_origen_id, r.sede_destino_id
            ORDER BY tasa, envios DESC
        """).fetchall()
        reporte = self._nuevo("envios",
                              "Envíos finalizados por ruta: recibidos sin problemas, con incidencias "
                              "(daño, faltante o destrucción) y extraviados.",
                              ["Ruta", "Envíos", "Exitosos", "Con incidencia", "Extraviados",
                               "Ejemplares afectados", "Tasa de éxito %"], filas)
        total = sum(f[1] for f in reporte.filas)
        exitosos = sum(f[2] for f in reporte.filas)
        incidencias = sum(f[3] for f in reporte.filas)
        extraviados = sum(f[4] for f in reporte.filas)
        reporte.totales = ["Total", total, exitosos, incidencias, extraviados,
                           sum(f[5] for f in reporte.filas), round(100 * exitosos / total, 1) if total else None]
        if total:
            reporte.grafico = Grafico("torta", "Resultado de los envíos",
                                      ["Exitosos", "Con incidencia", "Extraviados"],
                                      [exitosos, incidencias, extraviados])
        return reporte

    def _reporte_transito(self, cx) -> Reporte:
        filas = cx.execute("""
            WITH tiempos AS (
                SELECT r.id, r.sede_origen_id, r.sede_destino_id,
                       (julianday(MAX(CASE WHEN m.estado_nuevo IN ('RECIBIDO', 'RECIBIDO_CON_INCIDENCIA')
                                           THEN m.fecha_hora END))
                        - julianday(MIN(CASE WHEN m.estado_nuevo = 'DESPACHADO' THEN m.fecha_hora END))) * 24 AS horas,
                       (SELECT COUNT(*) FROM remito_detalle d WHERE d.remito_id = r.id) AS ejemplares
                FROM remito r
                JOIN remito_movimiento m ON m.remito_id = r.id
                WHERE r.estado IN ('RECIBIDO', 'RECIBIDO_CON_INCIDENCIA')
                GROUP BY r.id
            )
            SELECT so.nombre || ' → ' || sd.nombre AS ruta,
                   COUNT(*) AS remitos,
                   SUM(t.ejemplares) AS ejemplares,
                   ROUND(AVG(t.horas), 1) AS promedio,
                   ROUND(MIN(t.horas), 1) AS minimo,
                   ROUND(MAX(t.horas), 1) AS maximo
            FROM tiempos t
            JOIN sede so ON so.id = t.sede_origen_id
            JOIN sede sd ON sd.id = t.sede_destino_id
            GROUP BY t.sede_origen_id, t.sede_destino_id
            ORDER BY promedio DESC
        """).fetchall()
        reporte = self._nuevo("transito",
                              "Horas entre el despacho y la recepción de cada remito, por ruta. "
                              "Se calcula con el historial de movimientos del remito.",
                              ["Ruta", "Remitos", "Ejemplares movidos", "Promedio (h)", "Mínimo (h)", "Máximo (h)"],
                              filas)
        if reporte.filas:
            reporte.grafico = Grafico("barras_h", "Tiempo promedio de tránsito", [f[0] for f in reporte.filas],
                                      [f[3] for f in reporte.filas], "Horas")
            total = sum(f[1] for f in reporte.filas)
            promedio = sum(f[1] * f[3] for f in reporte.filas) / total
            reporte.totales = ["Toda la red", total, sum(f[2] for f in reporte.filas), round(promedio, 1),
                               min(f[4] for f in reporte.filas), max(f[5] for f in reporte.filas)]
        return reporte

    # -----------------------------------------------------------------------
    def resumen(self) -> dict:
        """Indicadores para la pantalla de inicio."""
        hoy = fecha_a_texto(self.ahora().date())
        with self._transaccion() as r:
            return dict(r.conexion.execute(f"""
                SELECT
                    (SELECT COUNT(*) FROM sede WHERE activa = 1) AS sedes,
                    (SELECT COUNT(*) FROM socio) AS socios,
                    (SELECT COUNT(*) FROM libro) AS libros,
                    (SELECT COUNT(*) FROM ejemplar WHERE estado NOT IN ('BAJA', 'EXTRAVIADO')) AS ejemplares,
                    (SELECT COUNT(*) FROM prestamo WHERE estado IN {ABIERTOS}) AS prestamos_abiertos,
                    (SELECT COUNT(*) FROM prestamo WHERE estado IN ('ACTIVO', 'VENCIDO')
                                                     AND fecha_vencimiento < :hoy) AS vencidos,
                    (SELECT COUNT(*) FROM remito
                      WHERE estado IN ('EN_PREPARACION', 'DESPACHADO', 'EN_TRANSITO')) AS remitos_en_curso,
                    (SELECT COUNT(*) FROM reserva WHERE estado IN ('PENDIENTE', 'ASIGNADA')) AS reservas,
                    (SELECT COALESCE(SUM(monto), 0) FROM sancion
                      WHERE tipo = 'MONETARIA' AND pagada = 0) AS multas_impagas
            """, {"hoy": hoy}).fetchone())
