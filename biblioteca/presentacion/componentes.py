"""Controles reutilizables de la interfaz. Solo presentación: no conocen servicios ni SQL."""
from __future__ import annotations

from typing import Callable

import flet as ft

from ..reportes.estructura import formatear
from .estilo import (HOVER, ACENTO_CLARO, LINEA, SUPERFICIE, SUPERFICIE_ALTA, FUENTE_SUBTITULO, TEXTO, TEXTO_SUAVE,
                     encabezado)

# Colores (fondo, letra) de las "pastillas" de estado
COLORES_ESTADO = {
    "verde": ("#E3F2EA", "#1F6B4A"),
    "azul": ("#E1ECF5", "#24527A"),
    "ambar": ("#FCF1DC", "#8A5A00"),
    "rojo": ("#FBE9E9", "#9B2C2C"),
    "gris": ("#EEF1F4", "#4A5560"),
}
ESTADOS = {
    "DISPONIBLE": "verde", "ACTIVO": "azul", "ACTIVA": "verde", "habilitado": "verde",
    "RECIBIDO": "verde", "CUMPLIDA": "verde", "DEVUELTO": "gris", "OK": "verde",
    "RESERVADO": "ambar", "PRESTADO": "azul", "EN_TRANSITO": "ambar", "DESPACHADO": "ambar",
    "EN_PREPARACION": "azul", "SOLICITADO": "azul", "LISTO_PARA_RETIRO": "verde",
    "PENDIENTE": "ambar", "ASIGNADA": "verde",
    "VENCIDO": "rojo", "EXTRAVIADO": "rojo", "RECIBIDO_CON_INCIDENCIA": "rojo", "FALTANTE": "rojo",
    "DESTRUIDO": "rojo", "DANIADO": "ambar", "BAJA": "gris", "DADA DE BAJA": "gris", "SEDE_DE_BAJA": "gris",
    "CANCELADO": "gris", "CANCELADA": "gris", "EXPIRADA": "gris", "ANULADO": "gris",
}


_ACENTOS = {"transito": "tránsito", "preparacion": "preparación", "daniado": "dañado"}
# Estados cuyo nombre en pantalla difiere del código guardado en la base
_ETIQUETAS = {"RESERVADO": "Apartado"}   # apartado para un préstamo o una reserva


def etiqueta_estado(texto: str) -> str:
    """EN_TRANSITO -> En tránsito"""
    if texto in _ETIQUETAS:
        return _ETIQUETAS[texto]
    if not texto.isupper():
        return texto
    palabras = [_ACENTOS.get(p, p) for p in texto.lower().split("_")]
    return " ".join(palabras).capitalize()


def pastilla(texto: str, color: str | None = None) -> ft.Control:
    clave = color or ESTADOS.get(texto, "rojo" if texto.startswith(("suspendido", "inhabilitado")) else "gris")
    fondo, letra = COLORES_ESTADO[clave]
    return ft.Container(
        content=ft.Text(etiqueta_estado(texto), size=12, color=letra, weight=ft.FontWeight.W_500),
        bgcolor=fondo, border_radius=3, padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, letra)),
    )


def titulo_pantalla(texto: str, subtitulo: str = "") -> ft.Control:
    controles: list[ft.Control] = [encabezado(texto, size=24)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=13, color=TEXTO_SUAVE, font_family=FUENTE_SUBTITULO))
    return ft.Column(controls=controles, spacing=2)


def boton(texto: str, icono, al_pulsar: Callable, principal: bool = False, deshabilitado: bool = False):
    clase = ft.FilledButton if principal else ft.OutlinedButton
    return clase(content=texto, icon=icono, on_click=al_pulsar, disabled=deshabilitado)


class Tabla:
    """DataTable con selección de una fila.

    `columnas`: lista de (título, numérica). Cada fila es (id, [valores]). Los valores que son
    controles se muestran tal cual; el resto se formatea como texto.
    """

    def __init__(self, columnas: list[tuple[str, bool]], al_seleccionar: Callable[[int | None], None] | None = None,
                 vacia: str = "No hay datos para mostrar."):
        self.al_seleccionar = al_seleccionar
        self.seleccionado: int | None = None
        self.tabla = ft.DataTable(
            # Encabezados en versalitas espaciadas, como los campos impresos de una ficha
            columns=[ft.DataColumn(label=ft.Text(t.upper(), size=11, color=TEXTO_SUAVE, weight=ft.FontWeight.W_600,
                                                 style=ft.TextStyle(letter_spacing=0.8)), numeric=n)
                     for t, n in columnas],
            rows=[], show_checkbox_column=False, column_spacing=22, heading_row_height=38,
            data_row_min_height=36, data_row_max_height=52,
            heading_row_color=SUPERFICIE_ALTA, data_text_style=ft.TextStyle(color=TEXTO, size=14),
            horizontal_lines=ft.BorderSide(1, LINEA),
            data_row_color={ft.ControlState.SELECTED: ACENTO_CLARO, ft.ControlState.HOVERED: HOVER},
        )
        self.vacia = ft.Text(vacia, italic=True, color=TEXTO_SUAVE, font_family=FUENTE_SUBTITULO, visible=False)

    def cargar(self, filas: list[tuple[int, list]]) -> None:
        ids = [i for i, _ in filas]
        if self.seleccionado not in ids:
            self.seleccionado = None
        self.tabla.rows = [
            ft.DataRow(
                cells=[ft.DataCell(v if isinstance(v, ft.Control) else ft.Text(formatear(v))) for v in valores],
                selected=(fila_id == self.seleccionado),
                on_select_change=(lambda e, i=fila_id: self._seleccionar(i)) if self.al_seleccionar else None,
                data=fila_id,
            )
            for fila_id, valores in filas
        ]
        self.vacia.visible = not filas

    def _seleccionar(self, fila_id: int) -> None:
        self.seleccionado = None if self.seleccionado == fila_id else fila_id
        for fila in self.tabla.rows:
            fila.selected = fila.data == self.seleccionado
        if self.al_seleccionar:
            self.al_seleccionar(self.seleccionado)

    def build(self, alto: int | None = None) -> ft.Control:
        contenido = ft.Column(controls=[ft.Row(controls=[self.tabla], scroll=ft.ScrollMode.AUTO), self.vacia],
                              scroll=ft.ScrollMode.AUTO, spacing=8)
        return ft.Container(content=contenido, height=alto, expand=alto is None, bgcolor=SUPERFICIE,
                            border=ft.Border.all(1, LINEA), border_radius=4,
                            padding=ft.Padding.only(bottom=8))


def opciones(pares) -> list[ft.DropdownOption]:
    return [ft.DropdownOption(key=str(clave), text=texto) for clave, texto in pares]


def desplegable(etiqueta: str, pares, valor=None, ancho: int | None = None, al_cambiar=None,
                filtrable: bool = False) -> ft.Dropdown:
    """Sin ancho fijo ocupa todo el ancho disponible."""
    return ft.Dropdown(label=etiqueta, options=opciones(pares), value=str(valor) if valor is not None else None,
                       width=ancho, on_select=al_cambiar, enable_filter=filtrable, editable=filtrable,
                       menu_height=320)


def campo(etiqueta: str, valor=None, ancho: int | None = None, **kwargs) -> ft.TextField:
    return ft.TextField(label=etiqueta, value="" if valor is None else str(valor), width=ancho, dense=True,
                        **kwargs)


def en_fila(*controles: ft.Control) -> ft.Row:
    """Pone controles uno al lado del otro repartiendo el ancho entre los que no tienen ancho fijo."""
    for control in controles:
        if getattr(control, "width", None) is None:
            control.expand = True
    return ft.Row(controls=list(controles), spacing=12)


def texto_o_none(control: ft.TextField) -> str | None:
    valor = (control.value or "").strip()
    return valor or None


def entero_o_none(control: ft.TextField, nombre: str) -> int | None:
    valor = texto_o_none(control)
    if valor is None:
        return None
    if not valor.isdigit():
        from ..modelo import ErrorNegocio
        raise ErrorNegocio(f"{nombre} debe ser un número entero")
    return int(valor)


def numero_o_none(control: ft.TextField, nombre: str) -> float | None:
    valor = texto_o_none(control)
    if valor is None:
        return None
    try:
        return float(valor.replace(".", "").replace(",", ".") if "," in valor else valor)
    except ValueError:
        from ..modelo import ErrorNegocio
        raise ErrorNegocio(f"{nombre} debe ser un número") from None


def id_seleccionado(control: ft.Dropdown, nombre: str) -> int:
    if not control.value:
        from ..modelo import ErrorNegocio
        raise ErrorNegocio(f"Seleccione {nombre}")
    return int(control.value)
