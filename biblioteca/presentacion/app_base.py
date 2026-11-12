"""Base común de las dos interfaces (personal y socios): navegación, mensajes y diálogos."""
from __future__ import annotations

from typing import Callable

import flet as ft

from ..modelo import ErrorNegocio
from ..servicios import Servicios
from .componentes import en_fila
from .estilo import ACENTO, ERROR, EXITO, LINEA, MENU, MENU_INDICADOR, MENU_TEXTO_SUAVE


class AplicacionBase:
    """Las subclases definen `self.pantallas` (cada una con build() y refrescar())."""

    def __init__(self, page: ft.Page, servicios: Servicios):
        self.page = page
        self.servicios = servicios
        self.pantallas: list = []
        self.contenido = ft.Container(expand=True, padding=ft.Padding.symmetric(horizontal=28, vertical=20))

    def crear_navegacion(self, cabecera: list[ft.Control], secciones: list[tuple]) -> ft.NavigationRail:
        """Menú lateral verde. `secciones`: (nombre, ícono, ícono seleccionado, clase de pantalla)."""
        return ft.NavigationRail(
            selected_index=0, extended=True, min_extended_width=214, bgcolor=MENU,
            indicator_color=MENU_INDICADOR, indicator_shape=ft.RoundedRectangleBorder(radius=3),
            selected_label_text_style=ft.TextStyle(color=ACENTO, size=14, weight=ft.FontWeight.W_600),
            unselected_label_text_style=ft.TextStyle(color=MENU_TEXTO_SUAVE, size=14),
            leading=ft.Container(
                content=ft.Column(controls=cabecera, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.only(top=22, bottom=18, left=8, right=8)),
            destinations=[ft.NavigationRailDestination(icon=ft.Icon(icono, color=MENU_TEXTO_SUAVE),
                                                       selected_icon=ft.Icon(icono_sel, color=ACENTO), label=nombre)
                          for nombre, icono, icono_sel, _ in secciones],
            on_change=self.cambiar_seccion,
        )

    def armar(self, navegacion: ft.NavigationRail, al_salir: Callable[[], None] | None) -> ft.Control:
        """Navegación a la izquierda (con "Salir" al pie si corresponde) y contenido a la derecha."""
        self.mostrar(0)
        navegacion.expand = True
        controles: list[ft.Control] = [navegacion]
        if al_salir is not None:
            controles.append(ft.Container(
                content=ft.TextButton(content="Salir", icon=ft.Icons.LOGOUT, on_click=lambda e: al_salir(),
                                      style=ft.ButtonStyle(color=MENU_TEXTO_SUAVE, icon_color=MENU_TEXTO_SUAVE)),
                padding=ft.Padding.only(left=14, bottom=14)))
        lateral = ft.Container(content=ft.Column(controls=controles, spacing=0), bgcolor=MENU,
                               border=ft.Border(right=ft.BorderSide(1, LINEA)))
        return ft.Row(controls=[lateral, self.contenido], expand=True, spacing=0)

    def cambiar_seccion(self, e) -> None:
        self.mostrar(e.control.selected_index)

    def mostrar(self, indice: int) -> None:
        pantalla = self.pantallas[indice]
        self.contenido.content = pantalla.build()
        self.ejecutar(pantalla.refrescar)

    # --- mensajes y diálogos -------------------------------------------------
    def notificar(self, mensaje: str, error: bool = False) -> None:
        self.page.show_dialog(ft.SnackBar(
            content=ft.Text(mensaje, color=ft.Colors.WHITE),
            bgcolor=ERROR[0] if error else EXITO[0], duration=6000 if error else 4500))

    def ejecutar(self, accion: Callable, *args, exito: str | None = None) -> bool:
        """Ejecuta una llamada a un servicio y muestra el error de negocio si lo hay."""
        try:
            resultado = accion(*args)
        except ErrorNegocio as error:
            self.notificar(str(error), error=True)
            return False
        except Exception as error:   # error inesperado: se informa sin cerrar la aplicación
            self.notificar(f"Error inesperado: {error}", error=True)
            raise
        mensaje = resultado if isinstance(resultado, str) and exito is None else exito
        if mensaje:
            self.notificar(mensaje)
        return True

    def ejecutar_y_refrescar(self, accion: Callable, *args, al_terminar: Callable, exito: str | None = None) -> bool:
        """Como ejecutar(), pero refresca la pantalla y la redibuja.

        notificar() abre un SnackBar con show_dialog(), que llama a update(); eso le indica a Flet
        que ya hubo un update en el evento y desactiva el redibujado automático de la pantalla.
        """
        ok = self.ejecutar(accion, *args, exito=exito)
        if ok:
            al_terminar()
        self.page.update()
        return ok

    def dialogo(self, titulo: str, controles: list[ft.Control], al_aceptar: Callable[[], str | None],
                texto_aceptar: str = "Guardar", ancho: int = 520, al_terminar: Callable | None = None) -> None:
        """Abre un formulario modal. Si `al_aceptar` no lanza ErrorNegocio, cierra y refresca.

        Los errores se muestran dentro del diálogo: un SnackBar quedaría tapado por el modal.
        """
        error_caja, error_texto, avisar = self._caja_mensaje()

        def mostrar_error(texto: str) -> None:
            avisar(texto, error=True)

        def aceptar(e):
            try:
                mensaje = al_aceptar()
            except ErrorNegocio as error:
                mostrar_error(str(error))
                return
            except Exception as error:   # error inesperado: se informa sin cerrar el formulario
                mostrar_error(f"Error inesperado: {error}")
                raise
            self.page.pop_dialog()
            if mensaje:
                self.notificar(mensaje)
            if al_terminar:
                al_terminar()
            # El evento nació en el diálogo: hay que pedir explícitamente que se redibuje la página
            self.page.update()

        # Los campos sueltos se ponen en una fila para que ocupen todo el ancho del diálogo
        controles = [en_fila(c) if isinstance(c, (ft.Dropdown, ft.TextField)) and c.width is None else c
                     for c in controles]
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo, weight=ft.FontWeight.BOLD),
            content=ft.Container(content=ft.Column(controls=controles + [error_caja], tight=True, spacing=14),
                                 width=ancho),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton(content=texto_aceptar, on_click=aceptar)],
            actions_alignment=ft.MainAxisAlignment.END,
            data=error_texto,   # permite a las pruebas leer el error mostrado
        )
        self.page.show_dialog(dialogo)

    def mostrar_detalle(self, titulo: str, controles: list[ft.Control], ancho: int = 560) -> Callable[..., bool]:
        """Diálogo de solo lectura con un único botón "Cerrar".

        Devuelve una función `ejecutar(accion, *args, exito=..., al_terminar=...)` para las acciones que se
        disparan desde el diálogo (por ejemplo, registrar un pago): el resultado o el error se muestran
        dentro del diálogo, porque un SnackBar quedaría tapado por el modal.
        """
        caja, texto, avisar = self._caja_mensaje()

        def ejecutar(accion: Callable, *args, exito: str | None = None, al_terminar: Callable | None = None) -> bool:
            try:
                resultado = accion(*args)
            except ErrorNegocio as error:
                avisar(str(error), error=True)
                return False
            if al_terminar:
                al_terminar()
            avisar(exito or (resultado if isinstance(resultado, str) else "Listo"))
            return True

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo, weight=ft.FontWeight.BOLD),
            content=ft.Container(content=ft.Column(controls=controles + [caja], tight=True, spacing=14,
                                                   scroll=ft.ScrollMode.AUTO), width=ancho),
            actions=[ft.FilledButton(content="Cerrar", on_click=lambda e: self.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
            data=texto,   # permite a las pruebas leer el mensaje mostrado
        ))
        return ejecutar

    def _caja_mensaje(self) -> tuple[ft.Container, ft.Text, Callable[..., None]]:
        """Recuadro oculto para mensajes dentro de un diálogo, y la función que lo muestra."""
        texto = ft.Text("", size=13, weight=ft.FontWeight.W_500)
        icono = ft.Icon(ft.Icons.ERROR_OUTLINE, size=20)
        caja = ft.Container(
            content=ft.Row(controls=[icono, ft.Container(content=texto, expand=True)], spacing=8),
            border_radius=8, padding=ft.Padding.symmetric(horizontal=12, vertical=8), visible=False)

        def avisar(mensaje: str, error: bool = False) -> None:
            color, fondo = ERROR if error else EXITO
            texto.value, texto.color, icono.color, caja.bgcolor = mensaje, color, color, fondo
            icono.icon = ft.Icons.ERROR_OUTLINE if error else ft.Icons.CHECK_CIRCLE_OUTLINE
            caja.visible = True
            self.page.update()

        return caja, texto, avisar

    def confirmar(self, titulo: str, texto: str, al_confirmar: Callable[[], str | None],
                  al_terminar: Callable | None = None) -> None:
        self.dialogo(titulo, [ft.Text(texto)], al_confirmar, texto_aceptar="Confirmar", ancho=420,
                     al_terminar=al_terminar)
