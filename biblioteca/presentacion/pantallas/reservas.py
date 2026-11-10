from __future__ import annotations

import flet as ft

from ...modelo import DIAS_PARA_RETIRAR, EstadoReserva
from ..componentes import Tabla, boton, desplegable, id_seleccionado, opciones, pastilla, titulo_pantalla


class PantallaReservas:
    def __init__(self, app):
        self.app = app
        self.filas: dict[int, dict] = {}
        self.solo_vigentes = ft.Switch(label="Solo vigentes", value=True, on_change=lambda e: self.refrescar())
        self.tabla = Tabla([("#", True), ("Fecha", False), ("Socio", False), ("Libro", False),
                            ("Sede de retiro", False), ("Estado", False), ("Ejemplar apartado", False),
                            ("Retirar hasta", False)],
                           self.al_seleccionar)
        self.btn_retirar = boton("Retirar", ft.Icons.HANDSHAKE, self.retirar, deshabilitado=True)
        self.btn_cancelar = boton("Cancelar reserva", ft.Icons.CANCEL_OUTLINED, self.cancelar, deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Reservas",
                            "Reserva de un título en una sede. Cuando hay un ejemplar libre se aparta y el socio "
                            f"tiene {DIAS_PARA_RETIRAR} días para retirarlo."),
            ft.Row(controls=[boton("Nueva reserva", ft.Icons.BOOKMARK_ADD, self.nueva, principal=True),
                             self.btn_retirar, self.btn_cancelar, ft.Container(expand=True), self.solo_vigentes]),
            self.tabla.build(),
        ], spacing=16, expand=True)

    def refrescar(self) -> None:
        filas = self.app.servicios.reservas.listar(self.solo_vigentes.value)
        self.filas = {f["id"]: f for f in filas}
        self.tabla.cargar([
            (f["id"], [f["id"], f["fecha_reserva"], f["socio"], f["titulo"], f["sede_retiro"], pastilla(f["estado"]),
                       f["codigo_inventario"],
                       f["fecha_expiracion"] if f["estado"] == EstadoReserva.ASIGNADA else None])
            for f in filas])
        self.al_seleccionar(self.tabla.seleccionado)

    def al_seleccionar(self, reserva_id: int | None) -> None:
        estado = self.filas[reserva_id]["estado"] if reserva_id in self.filas else None
        self.btn_retirar.disabled = estado != EstadoReserva.ASIGNADA
        self.btn_cancelar.disabled = estado not in EstadoReserva.VIGENTES

    def nueva(self, e) -> None:
        s = self.app.servicios
        socio = desplegable("Socio", [(f["id"], f"{f['apellido']}, {f['nombre']} · DNI {f['dni']}")
                                      for f in s.socios.listar()], filtrable=True)
        sede = desplegable("Sede de retiro", [(x.id, x.nombre) for x in s.sedes.listar(solo_activas=True)])
        libro = desplegable("Libro", [], filtrable=True)
        info = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        libros: dict[str, dict] = {}

        def al_elegir_sede(e=None):
            """Solo se ofrecen los títulos que la sede tiene en su catálogo."""
            libros.clear()
            if sede.value:
                libros.update({str(f["id"]): f for f in s.catalogo.libros_de_sede(int(sede.value))})
            libro.options = opciones([
                (clave, f"{f['titulo']} ({f['autor']}) · "
                        + (f"{f['disponibles']} disponible{'s' if f['disponibles'] > 1 else ''}"
                           if f["disponibles"] else "sin disponibles"))
                for clave, f in libros.items()])
            if libro.value not in libros:
                libro.value = None
            libro.disabled = not libros
            libro.hint_text = ("Seleccione primero una sede" if not sede.value else
                               None if libros else "La sede no tiene libros en su catálogo")
            al_elegir_libro()

        def al_elegir_libro(e=None):
            fila = libros.get(libro.value)
            if sede.value and not libros:
                info.value, info.color = "La sede no tiene libros en su catálogo para reservar.", "#8a1c1c"
                return
            info.color = ft.Colors.ON_SURFACE_VARIANT
            if fila is None:
                info.value = "Solo se pueden reservar títulos que la sede tenga en su catálogo."
            elif fila["disponibles"]:
                info.value = (f"Hay un ejemplar disponible: queda apartado y el socio tiene {DIAS_PARA_RETIRAR} "
                              "días para retirarlo.")
            else:
                info.value = ("No hay ejemplares disponibles ahora: la reserva queda en espera hasta que se "
                              "libere uno.")

        sede.on_select = al_elegir_sede
        libro.on_select = al_elegir_libro
        al_elegir_sede()

        def guardar():
            reserva = s.reservas.crear(id_seleccionado(socio, "el socio"), id_seleccionado(libro, "el libro"),
                                       id_seleccionado(sede, "la sede de retiro"))
            if reserva.estado == EstadoReserva.ASIGNADA:
                return (f"Reserva registrada. Hay un ejemplar apartado: retirar antes del "
                        f"{reserva.fecha_expiracion:%d/%m/%Y}.")
            return "Reserva registrada. Queda en espera hasta que se libere un ejemplar."

        self.app.dialogo("Nueva reserva", [socio, sede, libro, info],
                         guardar, texto_aceptar="Reservar", al_terminar=self.refrescar)

    def retirar(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        self.app.confirmar("Retirar reserva",
                           f"{fila['socio']} retira «{fila['titulo']}» ({fila['codigo_inventario']}). "
                           "Se registra un préstamo local.",
                           lambda: self.app.servicios.reservas.retirar(fila["id"]), al_terminar=self.refrescar)

    def cancelar(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        self.app.confirmar("Cancelar reserva", f"Se cancela la reserva de «{fila['titulo']}» de {fila['socio']}.",
                           lambda: self.app.servicios.reservas.cancelar(fila["id"]), al_terminar=self.refrescar)
