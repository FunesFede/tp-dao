"""Ayudas para probar la interfaz Flet sin abrir ventanas.

Una página falsa registra los diálogos y mensajes; las pruebas completan los formularios,
disparan los eventos y confirman, igual que lo haría el usuario.
"""
import flet as ft

from biblioteca.presentacion.estilo import ERROR


class PaginaFalsa:
    def __init__(self):
        self.dialogos = []
        self.mensajes = []
        self.controls = []   # lo que muestra la página (pantalla de ingreso o una de las aplicaciones)

    def add(self, *controles):
        self.controls.extend(controles)

    def show_dialog(self, dialogo):
        if isinstance(dialogo, ft.SnackBar):
            self.mensajes.append((dialogo.content.value, dialogo.bgcolor))
        else:
            self.dialogos.append(dialogo)

    def pop_dialog(self):
        return self.dialogos.pop()

    def update(self):
        pass

    # --- ayudas para las pruebas -------------------------------------------
    def campos(self):
        """Controles de entrada del diálogo abierto, en orden."""
        encontrados = []

        def recorrer(control):
            if isinstance(control, (ft.Dropdown, ft.TextField)):
                encontrados.append(control)
            for hijo in getattr(control, "controls", None) or []:
                recorrer(hijo)
            if getattr(control, "content", None) is not None and isinstance(control.content, ft.Control):
                recorrer(control.content)

        recorrer(self.dialogos[-1].content)
        return encontrados

    def textos(self):
        """Valores de todos los ft.Text del diálogo abierto, en orden."""
        encontrados = []

        def recorrer(control):
            if isinstance(control, ft.Text) and control.value:
                encontrados.append(control.value)
            for hijo in getattr(control, "controls", None) or []:
                recorrer(hijo)
            if getattr(control, "content", None) is not None and isinstance(control.content, ft.Control):
                recorrer(control.content)

        recorrer(self.dialogos[-1].content)
        return encontrados

    def aceptar(self):
        self.dialogos[-1].actions[-1].on_click(None)

    def ultimo_mensaje(self):
        return self.mensajes[-1][0]

    def hubo_error(self):
        return self.mensajes and self.mensajes[-1][1] == ERROR[0]

    def error_en_dialogo(self):
        """Error mostrado dentro del formulario abierto ("" si no hay)."""
        return self.dialogos[-1].data.value if self.dialogos else ""


def elegir(dropdown: ft.Dropdown, texto: str):
    """Selecciona la primera opción que contiene `texto` y dispara on_select."""
    opcion = next(o for o in dropdown.options if texto in o.text)
    dropdown.value = opcion.key
    if dropdown.on_select:
        dropdown.on_select(None)
