from __future__ import annotations

import flet as ft

from ...modelo import DIAS_PARA_RETIRAR, EstadoReserva
from ..componentes import Tabla, boton, pastilla, titulo_pantalla


class PantallaReservasSocio:
    def __init__(self, app):
        self.app = app
        self.filas: dict[int, dict] = {}
        self.tabla = Tabla([("Libro", False), ("Sede", False), ("Estado", False), ("Ejemplar apartado", False),
                            ("Retirar hasta", False)], self.al_seleccionar,
                           vacia="No tiene reservas. Puede reservar un libro desde el catálogo.")
        self.btn_cancelar = boton("Cancelar reserva", ft.Icons.CANCEL_OUTLINED, self.cancelar, deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Mis reservas",
                            f"Cuando se libera un ejemplar queda apartado y tiene {DIAS_PARA_RETIRAR} días "
                            "para retirarlo"),
            ft.Row(controls=[self.btn_cancelar]),
            self.tabla.build(),
        ], spacing=14, expand=True)

    def refrescar(self) -> None:
        filas = self.app.consulta.reservas(self.app.socio.id)
        self.filas = {f["id"]: f for f in filas}
        self.tabla.cargar([
            (f["id"], [f["titulo"], f["sede_retiro"], pastilla(f["estado"]), f["codigo_inventario"],
                       f["fecha_expiracion"] if f["estado"] == EstadoReserva.ASIGNADA else None])
            for f in filas])
        self.al_seleccionar(self.tabla.seleccionado)

    def al_seleccionar(self, reserva_id: int | None) -> None:
        fila = self.filas.get(reserva_id)
        self.btn_cancelar.disabled = fila is None or fila["estado"] not in EstadoReserva.VIGENTES

    def cancelar(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        self.app.confirmar("Cancelar reserva", f"¿Desea cancelar su reserva de «{fila['titulo']}»?",
                           lambda: self.app.consulta.cancelar_reserva(self.app.socio.id, fila["id"]),
                           al_terminar=self.refrescar)
