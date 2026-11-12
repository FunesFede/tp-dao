"""Estilo visual «institucional sobrio»: paleta, tipografías y tema de Flet.

Toda la interfaz toma los colores y las fuentes de acá; ninguna pantalla escribe colores a mano.
Fondo gris muy claro, superficies blancas con bordes finos, texto gris pizarra, un único acento
verde petróleo y todo en IBM Plex Sans (semibold para los títulos).
"""
from __future__ import annotations

import flet as ft

# --- paleta ------------------------------------------------------------------------
FONDO = "#F6F7F9"            # fondo general
SUPERFICIE = "#FFFFFF"       # tarjetas, tablas, diálogos y menú
SUPERFICIE_ALTA = "#EEF1F4"  # encabezados de tabla
TEXTO = "#1E2A33"            # texto principal (gris pizarra)
TEXTO_SUAVE = "#5B6874"      # etiquetas y texto secundario
LINEA = "#D5DAE0"            # bordes y separadores
LINEA_FUERTE = "#B4BCC6"     # borde de los campos de texto y de los botones
APAGADO = "#A3ACB6"          # texto e íconos de los controles deshabilitados
ACENTO = "#0F5C63"           # verde petróleo: botones principales, íconos, selección
ACENTO_CLARO = "#DCEDEE"     # fondo de lo seleccionado
HOVER = "#F3F5F7"            # fila de tabla bajo el mouse
MENU = SUPERFICIE            # menú lateral claro, separado del contenido por una línea
MENU_INDICADOR = ACENTO_CLARO
MENU_TEXTO = TEXTO
MENU_TEXTO_SUAVE = TEXTO_SUAVE

# Mensajes: (color del texto, color de fondo)
ERROR = ("#9B2C2C", "#FBE9E9")
EXITO = ("#1F6B4A", "#E3F2EA")
AVISO = ("#8A5A00", "#FCF1DC")

# --- tipografías ---------------------------------------------------------------------
# IBM Plex Sans (licencia OFL) incluida en assets/fonts/, así funciona sin conexión.
# Las rutas son relativas a la carpeta assets/ que Flet sirve junto a main.py.
FUENTE_TITULO = "Plex Semibold"
FUENTE_SUBTITULO = "Plex"
FUENTE_TEXTO = "Plex"
ALTERNATIVAS_TITULO = ["Segoe UI", "Noto Sans", "DejaVu Sans", "Arial"]
FUENTES = {
    FUENTE_TITULO: "fonts/IBMPlexSans-SemiBold.ttf",
    FUENTE_TEXTO: "fonts/IBMPlexSans-Regular.ttf",
}

_RECTO = ft.RoundedRectangleBorder(radius=4)


def tema() -> ft.Theme:
    esquema = ft.ColorScheme(
        primary=ACENTO, on_primary=SUPERFICIE, primary_container=ACENTO_CLARO, on_primary_container=ACENTO,
        secondary=ACENTO, on_secondary=SUPERFICIE, secondary_container=ACENTO_CLARO, on_secondary_container=ACENTO,
        surface=FONDO, on_surface=TEXTO, on_surface_variant=TEXTO_SUAVE, surface_tint=FONDO,
        surface_container_lowest=SUPERFICIE, surface_container_low=SUPERFICIE, surface_container=SUPERFICIE,
        surface_container_high=SUPERFICIE, surface_container_highest=SUPERFICIE_ALTA,
        outline=LINEA_FUERTE, outline_variant=LINEA,
        error=ERROR[0], on_error=SUPERFICIE, error_container=ERROR[1], on_error_container=ERROR[0],
    )
    return ft.Theme(
        color_scheme=esquema,
        font_family=FUENTE_TEXTO,
        scaffold_bgcolor=FONDO,
        divider_color=LINEA,
        # Colores por estado: un color fijo pisaría el aspecto atenuado de los botones deshabilitados
        filled_button_theme=ft.FilledButtonTheme(style=ft.ButtonStyle(
            shape=_RECTO, elevation=0,
            bgcolor={ft.ControlState.DISABLED: SUPERFICIE_ALTA, ft.ControlState.DEFAULT: ACENTO},
            color={ft.ControlState.DISABLED: APAGADO, ft.ControlState.DEFAULT: SUPERFICIE},
            icon_color={ft.ControlState.DISABLED: APAGADO, ft.ControlState.DEFAULT: SUPERFICIE})),
        outlined_button_theme=ft.OutlinedButtonTheme(style=ft.ButtonStyle(
            shape=_RECTO, bgcolor={ft.ControlState.DEFAULT: SUPERFICIE},
            color={ft.ControlState.DISABLED: APAGADO, ft.ControlState.DEFAULT: TEXTO},
            icon_color={ft.ControlState.DISABLED: APAGADO, ft.ControlState.DEFAULT: ACENTO},
            side={ft.ControlState.DISABLED: ft.BorderSide(1, LINEA),
                  ft.ControlState.DEFAULT: ft.BorderSide(1, LINEA_FUERTE)})),
        text_button_theme=ft.TextButtonTheme(style=ft.ButtonStyle(shape=_RECTO)),
        dialog_theme=ft.DialogTheme(
            bgcolor=SUPERFICIE, shape=ft.RoundedRectangleBorder(radius=6),
            title_text_style=ft.TextStyle(font_family=FUENTE_TITULO, size=18, color=TEXTO)),
    )


def aplicar(page: ft.Page) -> None:
    """Fuentes, tema y fondo de la página."""
    page.fonts = FUENTES
    page.theme = tema()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = FONDO


def encabezado(texto: str = "", size: int = 16, color: str = TEXTO, **kwargs) -> ft.Text:
    """Texto de título (IBM Plex Sans semibold)."""
    return ft.Text(texto, size=size, color=color, font_family=FUENTE_TITULO,
                   font_family_fallback=ALTERNATIVAS_TITULO, **kwargs)
