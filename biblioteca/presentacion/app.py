"""Ventana principal: navegación entre pantallas, mensajes y diálogos.

Cada pantalla es una clase convencional con build() (guía de Flet de la cátedra) y solo llama
a los servicios; ninguna pantalla escribe SQL ni aplica reglas de negocio.
"""
from __future__ import annotations

from typing import Callable

import flet as ft

from .. import NOMBRE_RED
from ..servicios import Servicios
from .app_base import AplicacionBase
from .componentes import AZUL
from .pantallas.catalogo import PantallaCatalogo
from .pantallas.inicio import PantallaInicio
from .pantallas.prestamos import PantallaPrestamos
from .pantallas.remitos import PantallaRemitos
from .pantallas.reportes import PantallaReportes
from .pantallas.reservas import PantallaReservas
from .pantallas.sedes import PantallaSedes
from .pantallas.socios import PantallaSocios

SECCIONES = [
    ("Inicio", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD, PantallaInicio),
    ("Sedes", ft.Icons.STORE_OUTLINED, ft.Icons.STORE, PantallaSedes),
    ("Socios", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE, PantallaSocios),
    ("Catálogo", ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.MENU_BOOK, PantallaCatalogo),
    ("Préstamos", ft.Icons.SWAP_HORIZ_OUTLINED, ft.Icons.SWAP_HORIZ, PantallaPrestamos),
    ("Remitos", ft.Icons.LOCAL_SHIPPING_OUTLINED, ft.Icons.LOCAL_SHIPPING, PantallaRemitos),
    ("Reservas", ft.Icons.BOOKMARK_BORDER, ft.Icons.BOOKMARK, PantallaReservas),
    ("Reportes", ft.Icons.BAR_CHART_OUTLINED, ft.Icons.BAR_CHART, PantallaReportes),
]


class AplicacionBiblioteca(AplicacionBase):
    """Interfaz del personal de la biblioteca."""

    def __init__(self, page: ft.Page, servicios: Servicios, al_salir: Callable[[], None] | None = None):
        super().__init__(page, servicios)
        self.al_salir = al_salir
        self.pantallas = [clase(self) for _, _, _, clase in SECCIONES]
        self.navegacion = ft.NavigationRail(
            selected_index=0, extended=True, min_extended_width=190,
            leading=ft.Container(
                content=ft.Column(controls=[
                    ft.Icon(ft.Icons.LOCAL_LIBRARY, color=AZUL, size=34),
                    ft.Text(NOMBRE_RED, weight=ft.FontWeight.BOLD, color=AZUL, width=170,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text("Préstamos interbibliotecarios", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.only(top=16, bottom=12)),
            destinations=[ft.NavigationRailDestination(icon=icono, selected_icon=icono_sel, label=nombre)
                          for nombre, icono, icono_sel, _ in SECCIONES],
            on_change=self.cambiar_seccion,
        )

    def build(self) -> ft.Control:
        return self.armar(self.navegacion, self.al_salir)


def main(page: ft.Page) -> None:
    from ..datos.conexion import inicializar_base
    page.title = f"{NOMBRE_RED} · Préstamos interbibliotecarios"
    page.theme = ft.Theme(color_scheme_seed=AZUL)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.width = 1360
    page.window.height = 860
    page.window.min_width = 1100
    page.window.min_height = 680

    inicializar_base()
    servicios = Servicios()
    servicios.procesar_vencimientos()
    from .ingreso import abrir_ingreso   # import local: ingreso importa esta clase
    abrir_ingreso(page, servicios)
