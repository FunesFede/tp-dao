from __future__ import annotations

import flet as ft

from ...modelo import EstadoPrestamo, TipoPrestamo
from ..componentes import Tabla, desplegable, pastilla, titulo_pantalla
from ..estilo import EXITO

VISTAS = {"abiertos": "Abiertos", "historial": "Historial"}


class PantallaPrestamosSocio:
    def __init__(self, app):
        self.app = app
        self.vista = desplegable("Mostrar", list(VISTAS.items()), "abiertos", ancho=200,
                                 al_cambiar=lambda e: self.refrescar())
        self.tabla = Tabla([("Libro", False), ("Tipo", False), ("Retira en", False), ("Estado", False),
                            ("Vence", False), ("Atraso", False)],
                           vacia="No tiene préstamos para mostrar.")
        self.avisos = ft.Column(spacing=6)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Mis préstamos", "Préstamos abiertos e historial de los ya cerrados"),
            self.vista,
            self.avisos,
            self.tabla.build(),
        ], spacing=14, expand=True)

    def refrescar(self) -> None:
        abiertos = (self.vista.value or "abiertos") == "abiertos"
        filas = self.app.consulta.prestamos(self.app.socio.id, abiertos)
        self.tabla.cargar([
            (f["id"], [f["titulo"], "Interbibliotecario" if f["tipo"] == TipoPrestamo.INTER else "Local",
                       f["sede_destino"], pastilla(f["estado"]), f["fecha_vencimiento"],
                       f"{f['dias_atraso']} día(s)" if f["dias_atraso"] else ""])
            for f in filas])
        self.avisos.controls = [
            ft.Container(content=ft.Text(f"«{f['titulo']}» ya llegó. Puede retirarlo en «{f['sede_destino']}».",
                                         color=EXITO[0]),
                         bgcolor=EXITO[1], padding=10, border_radius=3)
            for f in filas if f["estado"] == EstadoPrestamo.LISTO_PARA_RETIRO]
