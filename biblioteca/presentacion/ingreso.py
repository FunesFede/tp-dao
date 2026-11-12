"""Pantalla de ingreso: elige entre la interfaz del personal y la consulta de socios."""
from __future__ import annotations

import flet as ft

from .. import NOMBRE_RED
from ..modelo import ErrorNegocio
from ..servicios import Servicios
from .app import AplicacionBiblioteca
from .app_socio import AplicacionSocio
from .componentes import campo
from .estilo import ACENTO, ERROR, LINEA, SUPERFICIE, FUENTE_SUBTITULO, TEXTO_SUAVE, encabezado


def cambiar_contenido(page: ft.Page, control: ft.Control) -> None:
    """Reemplaza todo lo que muestra la página por `control`."""
    page.controls.clear()
    page.add(control)
    page.update()


def abrir_ingreso(page: ft.Page, servicios: Servicios) -> None:
    cambiar_contenido(page, PantallaIngreso(page, servicios).build())


class PantallaIngreso:
    def __init__(self, page: ft.Page, servicios: Servicios):
        self.page = page
        self.servicios = servicios
        self.dni = campo("DNI", hint_text="Sin puntos", on_submit=self.ingresar_socio)
        self.clave = campo("Clave", hint_text="Clave de personal", on_submit=self.ingresar_personal, autofocus=True, password=True, can_reveal_password=True)
        self.error = ft.Text("", color=ERROR[0], size=13, visible=False)
        self.error_personal = ft.Text("", color=ERROR[0], size=13, visible=False)
        self.aplicacion: AplicacionBiblioteca | AplicacionSocio | None = None   # la que se abrió al ingresar

    def build(self) -> ft.Control:
        personal = self._tarjeta(
            ft.Icons.BADGE_OUTLINED, "Personal de la biblioteca",
            "Sedes, socios, catálogo, préstamos, remitos, reservas y reportes.",
            [self.clave, self.error_personal, ft.FilledButton(content="Ingresar", icon=ft.Icons.LOGIN, on_click=self.ingresar_personal)])
        socios = self._tarjeta(
            ft.Icons.PERSON_OUTLINE, "Socios",
            "Consulte el catálogo, sus préstamos, sus reservas y su situación.",
            [self.dni, self.error,
             ft.FilledButton(content="Consultar", icon=ft.Icons.SEARCH, on_click=self.ingresar_socio)])
        return ft.Container(
            content=ft.Column(controls=[
                ft.Icon(ft.Icons.LOCAL_LIBRARY, color=ACENTO, size=40),
                encabezado(NOMBRE_RED, size=28, text_align=ft.TextAlign.CENTER),
                ft.Text("Sistema de préstamos interbibliotecarios", size=16, color=TEXTO_SUAVE,
                        font_family=FUENTE_SUBTITULO),
                ft.Container(height=16),
                ft.Row(controls=[personal, socios], spacing=24, alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.START),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER,
                spacing=6),
            expand=True, alignment=ft.Alignment.CENTER, padding=24,
        )

    @staticmethod
    def _tarjeta(icono, titulo: str, descripcion: str, controles: list[ft.Control]) -> ft.Control:
        return ft.Container(
            content=ft.Column(controls=[
                ft.Row(controls=[ft.Icon(icono, color=ACENTO, size=24), encabezado(titulo, size=18)]),
                ft.Text(descripcion, size=13, color=TEXTO_SUAVE),
                ft.Container(height=4),
                *controles,
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            width=340, padding=24, border_radius=4, bgcolor=SUPERFICIE,
            border=ft.Border.all(1, LINEA),
        )

    # --- eventos ---------------------------------------------------------------
    def _volver(self) -> None:
        abrir_ingreso(self.page, self.servicios)

    def ingresar_personal(self, e) -> None:
        if self.clave.value != "PERSONAL123":
            self.error_personal.value = "Clave incorrecta"
            self.error_personal.visible = True
            self.page.update()
            return

        self.aplicacion = AplicacionBiblioteca(self.page, self.servicios, al_salir=self._volver)
        cambiar_contenido(self.page, self.aplicacion.build())

    def ingresar_socio(self, e) -> None:
        try:
            socio = self.servicios.consulta_socio.ingresar(self.dni.value)
        except ErrorNegocio as error:
            self.error.value = str(error)
            self.error.visible = True
            self.page.update()
            return
        self.aplicacion = AplicacionSocio(self.page, self.servicios, socio, al_salir=self._volver)
        cambiar_contenido(self.page, self.aplicacion.build())
