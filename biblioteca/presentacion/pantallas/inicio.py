from __future__ import annotations

import flet as ft

from ...modelo.sancion import pesos
from ..componentes import AZUL, boton, titulo_pantalla


class PantallaInicio:
    INDICADORES = [
        ("sedes", "Sedes activas", ft.Icons.STORE),
        ("socios", "Socios", ft.Icons.PEOPLE),
        ("libros", "Títulos en catálogo", ft.Icons.MENU_BOOK),
        ("ejemplares", "Ejemplares en circulación", ft.Icons.LIBRARY_BOOKS),
        ("prestamos_abiertos", "Préstamos abiertos", ft.Icons.SWAP_HORIZ),
        ("vencidos", "Préstamos vencidos", ft.Icons.WARNING_AMBER),
        ("remitos_en_curso", "Remitos en curso", ft.Icons.LOCAL_SHIPPING),
        ("reservas", "Reservas vigentes", ft.Icons.BOOKMARK),
        ("multas_impagas", "Multas impagas", ft.Icons.PAYMENTS),
    ]

    def __init__(self, app):
        self.app = app
        self.valores = {clave: ft.Text("-", size=28, weight=ft.FontWeight.BOLD, color=AZUL)
                        for clave, _, _ in self.INDICADORES}

    def build(self) -> ft.Control:
        tarjetas = [
            ft.Container(
                content=ft.Column(controls=[
                    ft.Row(controls=[ft.Icon(icono, color=AZUL, size=20),
                                     ft.Text(nombre, size=13, color=ft.Colors.ON_SURFACE_VARIANT)]),
                    self.valores[clave],
                ], spacing=6),
                width=230, padding=16, border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.05, AZUL),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, AZUL)),
            )
            for clave, nombre, icono in self.INDICADORES
        ]
        return ft.Column(controls=[
            ft.Row(controls=[
                titulo_pantalla("Inicio", "Estado general de la red de bibliotecas"),
                boton("Procesar vencimientos", ft.Icons.UPDATE, self.procesar_vencimientos),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row(controls=tarjetas, wrap=True, spacing=16, run_spacing=16),
            ft.Text("Los préstamos vencidos y las reservas no retiradas se actualizan automáticamente al "
                    "iniciar la aplicación. Use «Procesar vencimientos» para actualizarlos manualmente.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=24, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar(self) -> None:
        datos = self.app.servicios.reportes.resumen()
        for clave, texto in self.valores.items():
            valor = datos[clave]
            texto.value = pesos(valor) if clave == "multas_impagas" else str(valor)

    def procesar_vencimientos(self, e) -> None:
        self.app.ejecutar_y_refrescar(self.app.servicios.procesar_vencimientos, al_terminar=self.refrescar)
