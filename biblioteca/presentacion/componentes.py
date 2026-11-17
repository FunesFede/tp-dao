"""Controles reutilizables de la interfaz. Solo presentación: no conocen servicios ni SQL."""
from __future__ import annotations

from typing import Callable

import flet as ft

from ..modelo.texto import coincide
from ..reportes.estructura import formatear
from .estilo import (ACENTO, ACENTO_CLARO, FUENTE_SUBTITULO, HOVER, LINEA, LINEA_FUERTE, SUPERFICIE, SUPERFICIE_ALTA,
                     TEXTO, TEXTO_SUAVE, encabezado)

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
_ETIQUETAS = {"RESERVADO": "Apartado",   # apartado para un préstamo o una reserva
              "OK": "Correcto"}           # resultado de recepción


def mayuscula_inicial(texto: str) -> str:
    """Primera letra en mayúscula sin tocar el resto (capitalize() pasaría a minúscula fechas o nombres)."""
    return texto[:1].upper() + texto[1:]


def etiqueta_estado(texto: str) -> str:
    """EN_TRANSITO -> En tránsito; "suspendido hasta el ..." -> "Suspendido hasta el ..." """
    if texto in _ETIQUETAS:
        return _ETIQUETAS[texto]
    if not texto.isupper():
        return mayuscula_inicial(texto)
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
        # El desplazamiento horizontal envuelve al vertical para que su barra quede siempre al pie del
        # recuadro: si la tabla no entra a lo ancho, se ve que hay más columnas sin bajar hasta el final
        filas = ft.Column(controls=[self.tabla, self.vacia], scroll=ft.ScrollMode.AUTO, spacing=8)
        contenido = ft.Row(controls=[filas], scroll=ft.ScrollMode.ALWAYS,
                           vertical_alignment=ft.CrossAxisAlignment.START)
        return ft.Container(content=contenido, height=alto, expand=alto is None, bgcolor=SUPERFICIE,
                            border=ft.Border.all(1, LINEA), border_radius=4,
                            padding=ft.Padding.only(bottom=8))


def opciones(pares) -> list[ft.DropdownOption]:
    return [ft.DropdownOption(key=str(clave), text=texto) for clave, texto in pares]


def desplegable(etiqueta: str, pares, valor=None, ancho: int | None = None, al_cambiar=None) -> ft.Dropdown:
    """Sin ancho fijo ocupa todo el ancho disponible. Para buscar entre muchas opciones, sumarle un buscador()."""
    return ft.Dropdown(label=etiqueta, options=opciones(pares), value=str(valor) if valor is not None else None,
                       width=ancho, on_select=al_cambiar, menu_height=320)


class Selector(ft.Stack):
    """Un solo campo para elegir una opción: se despliega al tocarlo y se filtra mientras se escribe.

    La búsqueda toma cada palabra en cualquier orden, sin distinguir tildes, mayúsculas ni signos
    («tomas herrera» encuentra «Herrera, Tomás»). Enter elige la primera coincidencia.

    Se usa igual que un desplegable: `value` (clave elegida o None), `options` (lista de DropdownOption),
    `on_select` y `hint_text`. No es un ft.Dropdown porque, en Flet 1.x, cambiar las opciones de un
    desplegable mientras se escribe en él le quita el foco; el SearchBar arma su lista desde Python sin
    ese problema. La etiqueta flotante imita la de los demás campos.
    """

    def __init__(self, etiqueta: str, pares=(), al_cambiar=None):
        self._value: str | None = None
        self._options: list[ft.DropdownOption] = opciones(pares)
        self.on_select = al_cambiar
        self._barra = ft.SearchBar(
            bar_hint_text="Escriba para buscar", view_hint_text=f"Buscar {etiqueta.lower()}",
            bar_trailing=[ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=TEXTO_SUAVE)],
            bar_bgcolor=SUPERFICIE, bar_elevation=0, bar_shape=ft.RoundedRectangleBorder(radius=4),
            bar_border_side={ft.ControlState.FOCUSED: ft.BorderSide(2, ACENTO),
                             ft.ControlState.DEFAULT: ft.BorderSide(1, LINEA_FUERTE)},
            bar_overlay_color=ft.Colors.TRANSPARENT, bar_padding=ft.Padding.symmetric(horizontal=8),
            bar_text_style=ft.TextStyle(size=16, color=TEXTO),
            bar_hint_text_style=ft.TextStyle(size=16, color=TEXTO_SUAVE),
            bar_size_constraints=ft.BoxConstraints(min_height=48, max_height=48),
            view_bgcolor=SUPERFICIE, view_elevation=4, view_shape=ft.RoundedRectangleBorder(radius=4),
            view_size_constraints=ft.BoxConstraints(max_height=320),
            on_tap=self._abrir, on_change=self._al_escribir, on_submit=self._al_confirmar,
            on_tap_outside_view=self._al_salir,
        )
        etiqueta_flotante = ft.Container(
            content=ft.Text(etiqueta, size=12, color=TEXTO_SUAVE), bgcolor=SUPERFICIE,
            padding=ft.Padding.symmetric(horizontal=4), left=8, top=0)
        super().__init__(controls=[ft.Container(content=self._barra, padding=ft.Padding.only(top=8)),
                                   etiqueta_flotante], height=56)

    # --- interfaz de desplegable ----------------------------------------------
    @property
    def value(self) -> str | None:
        return self._value

    @value.setter
    def value(self, clave: str | None) -> None:
        self._value = clave
        self._barra.value = self._texto(clave)

    @property
    def options(self) -> list[ft.DropdownOption]:
        return self._options

    @options.setter
    def options(self, nuevas: list[ft.DropdownOption]) -> None:
        self._options = nuevas
        self._barra.controls = self._items(self._barra.value)

    @property
    def hint_text(self) -> str | None:
        return self._barra.bar_hint_text

    @hint_text.setter
    def hint_text(self, texto: str | None) -> None:
        self._barra.bar_hint_text = texto or "Escriba para buscar"

    # --- búsqueda ----------------------------------------------------------
    def coincidencias(self, texto: str | None) -> list[ft.DropdownOption]:
        """Opciones que corresponden a lo escrito. Con la opción elegida a la vista, se ofrecen todas."""
        if not texto or texto == self._texto(self._value):
            return list(self._options)
        return [o for o in self._options if coincide(texto, o.text)]

    def elegir(self, clave: str | None) -> None:
        """Elige una opción (o ninguna) y avisa a on_select si cambió."""
        anterior = self._value
        self.value = clave
        if clave != anterior and self.on_select:
            self.on_select(None)

    def _texto(self, clave: str | None) -> str:
        return next((o.text for o in self._options if o.key == clave), "")

    def _items(self, texto: str | None) -> list[ft.Control]:
        encontradas = self.coincidencias(texto)
        if not encontradas:
            return [ft.ListTile(title=ft.Text("Sin coincidencias", italic=True, color=TEXTO_SUAVE), dense=True)]
        return [ft.ListTile(title=ft.Text(o.text, size=14), data=o.key, dense=True, on_click=self._al_elegir,
                            selected=o.key == self._value, selected_tile_color=ACENTO_CLARO)
                for o in encontradas]

    # --- eventos -----------------------------------------------------------
    async def _abrir(self, e) -> None:
        self._barra.controls = self._items(self._barra.value)
        await self._barra.open_view()

    def _al_escribir(self, e) -> None:
        texto = e.data or ""
        if self._value is not None and texto != self._texto(self._value):
            # Lo escrito ya no es la opción elegida. No se toca el texto de la barra: cambiarlo
            # mientras se escribe pisaría lo que el usuario está tipeando.
            self._value = None
            if self.on_select:
                self.on_select(None)
        self._barra.controls = self._items(texto)
        e.page.update()

    async def _al_elegir(self, e) -> None:
        self.elegir(e.control.data)
        await self._barra.close_view(self._texto(self._value))
        e.page.update()

    async def _al_confirmar(self, e) -> None:
        encontradas = self.coincidencias(e.data)
        if encontradas:
            self.elegir(encontradas[0].key)
        await self._barra.close_view(self._texto(self._value))
        e.page.update()

    async def _al_salir(self, e) -> None:
        await self._barra.close_view(self._texto(self._value))


def selector(etiqueta: str, pares, al_cambiar=None) -> Selector:
    """Campo para elegir entre muchas opciones buscando por texto (socios, libros)."""
    return Selector(etiqueta, pares, al_cambiar)


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


def id_seleccionado(control: ft.Dropdown | Selector, nombre: str) -> int:
    if not control.value:
        from ..modelo import ErrorNegocio
        raise ErrorNegocio(f"Seleccione {nombre}")
    return int(control.value)
