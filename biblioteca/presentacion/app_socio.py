"""Interfaz de consulta para socios: catálogo, préstamos, reservas y situación del socio que ingresó.

Las pantallas solo usan `servicios.consulta_socio` y las dos lecturas del catálogo
(`listar_libros` y `disponibilidad`), que no exponen datos de otros socios.
"""
from __future__ import annotations

from typing import Callable

import flet as ft

from .. import NOMBRE_RED
from ..modelo import Socio
from ..servicios import Servicios
from .app_base import AplicacionBase
from .componentes import AZUL, pastilla
from .pantallas_socio.catalogo import PantallaCatalogoSocio
from .pantallas_socio.prestamos import PantallaPrestamosSocio
from .pantallas_socio.reservas import PantallaReservasSocio
from .pantallas_socio.situacion import PantallaSituacionSocio

SECCIONES_SOCIO = [
    ("Catálogo", ft.Icons.MENU_BOOK_OUTLINED, ft.Icons.MENU_BOOK, PantallaCatalogoSocio),
    ("Mis préstamos", ft.Icons.SWAP_HORIZ_OUTLINED, ft.Icons.SWAP_HORIZ, PantallaPrestamosSocio),
    ("Mis reservas", ft.Icons.BOOKMARK_BORDER, ft.Icons.BOOKMARK, PantallaReservasSocio),
    ("Mi situación", ft.Icons.ACCOUNT_CIRCLE_OUTLINED, ft.Icons.ACCOUNT_CIRCLE, PantallaSituacionSocio),
]


def pastilla_situacion(situacion: str) -> ft.Control:
    """habilitado / suspendido hasta... / inhabilitado: ... -> pastilla corta con su color."""
    if situacion.startswith("suspendido"):
        return pastilla("Suspendido", "rojo")
    if situacion.startswith("inhabilitado"):
        return pastilla("Inhabilitado", "rojo")
    return pastilla("Habilitado", "verde")


class AplicacionSocio(AplicacionBase):
    def __init__(self, page: ft.Page, servicios: Servicios, socio: Socio, al_salir: Callable[[], None]):
        super().__init__(page, servicios)
        self.socio = socio
        self.al_salir = al_salir
        self.pantallas = [clase(self) for _, _, _, clase in SECCIONES_SOCIO]

    @property
    def consulta(self):
        return self.servicios.consulta_socio

    def build(self) -> ft.Control:
        situacion = self.consulta.situacion(self.socio.id)["situacion"]
        navegacion = ft.NavigationRail(
            selected_index=0, extended=True, min_extended_width=200,
            leading=ft.Container(
                content=ft.Column(controls=[
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color=AZUL, size=40),
                    ft.Text(f"{self.socio.nombre} {self.socio.apellido}", weight=ft.FontWeight.BOLD,
                            color=AZUL, width=180, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"DNI {self.socio.dni}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    pastilla_situacion(situacion),
                    ft.Text(NOMBRE_RED, size=10, color=ft.Colors.ON_SURFACE_VARIANT, width=180,
                            text_align=ft.TextAlign.CENTER),
                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.only(top=16, bottom=12)),
            destinations=[ft.NavigationRailDestination(icon=icono, selected_icon=icono_sel, label=nombre)
                          for nombre, icono, icono_sel, _ in SECCIONES_SOCIO],
            on_change=self.cambiar_seccion,
        )
        return self.armar(navegacion, self.al_salir)
