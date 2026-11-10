from __future__ import annotations

from datetime import datetime

import flet as ft

from ...datos.conexion import RAIZ_PROYECTO
from ...reportes.estructura import Reporte, formatear
from ...reportes.exportador_csv import exportar_csv
from ...reportes.exportador_pdf import exportar_pdf
from ...reportes.graficos import grafico_png
from ..componentes import AZUL, Tabla, boton, titulo_pantalla

CARPETA_EXPORTES = RAIZ_PROYECTO / "exportes"


class PantallaReportes:
    def __init__(self, app):
        self.app = app
        self.reporte: Reporte | None = None
        self.clave = "prestamos_activos"
        self.lista = ft.Column(spacing=2)
        self.titulo = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color=AZUL)
        self.descripcion = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.grafico = ft.Container()
        self.contenedor_tabla = ft.Column()
        self.btn_pdf = boton("Exportar PDF", ft.Icons.PICTURE_AS_PDF, self.exportar_pdf, principal=True)
        self.btn_csv = boton("Exportar CSV", ft.Icons.TABLE_VIEW, self.exportar_csv)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Reportes", "Consultas de gestión, exportables a PDF (con gráfico) y CSV"),
            ft.Row(controls=[
                ft.Container(content=self.lista, width=290,
                             border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=8, padding=6),
                ft.Column(controls=[
                    ft.Row(controls=[ft.Column(controls=[self.titulo, self.descripcion], spacing=4, expand=True),
                                     self.btn_pdf, self.btn_csv], vertical_alignment=ft.CrossAxisAlignment.START),
                    self.grafico,
                    self.contenedor_tabla,
                ], expand=True, spacing=14, scroll=ft.ScrollMode.AUTO),
            ], expand=True, spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
        ], spacing=16, expand=True)

    def refrescar(self) -> None:
        self.lista.controls = [
            ft.ListTile(title=ft.Text(nombre, size=14), selected=clave == self.clave, dense=True,
                        selected_tile_color=ft.Colors.with_opacity(0.1, AZUL), selected_color=AZUL,
                        on_click=lambda e, c=clave: self.seleccionar(c))
            for clave, nombre in self.app.servicios.reportes.CATALOGO.items()
        ]
        self._generar()

    def seleccionar(self, clave: str) -> None:
        self.clave = clave
        self.refrescar()

    def _generar(self) -> None:
        self.reporte = r = self.app.servicios.reportes.generar(self.clave)
        self.titulo.value = r.titulo
        self.descripcion.value = f"{r.descripcion} Generado el {r.generado:%d/%m/%Y %H:%M}."
        if r.grafico and any(r.grafico.valores):
            self.grafico.content = ft.Image(src=grafico_png(r.grafico).getvalue(), width=760)
            self.grafico.visible = True
        else:
            self.grafico.visible = False
        tabla = Tabla([(c, isinstance(r.filas[0][i], (int, float)) if r.filas else False)
                       for i, c in enumerate(r.columnas)], vacia="No hay datos para este reporte.")
        filas = [(i, f) for i, f in enumerate(r.filas)]
        if r.totales and r.filas:
            totales = (list(r.totales) + [""] * len(r.columnas))[:len(r.columnas)]
            filas.append((-1, [ft.Text(formatear(v) if v != "" else "", weight=ft.FontWeight.BOLD)
                               for v in totales]))
        tabla.cargar(filas)
        self.contenedor_tabla.controls = [tabla.build()]

    def _ruta(self, extension: str):
        return CARPETA_EXPORTES / f"{self.clave}_{datetime.now():%Y%m%d_%H%M%S}.{extension}"

    def exportar_pdf(self, e) -> None:
        self.app.ejecutar(lambda: f"PDF guardado en {exportar_pdf(self.reporte, self._ruta('pdf'))}")

    def exportar_csv(self, e) -> None:
        self.app.ejecutar(lambda: f"CSV guardado en {exportar_csv(self.reporte, self._ruta('csv'))}")
