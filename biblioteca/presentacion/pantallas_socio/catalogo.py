from __future__ import annotations

import flet as ft

from ...modelo import DIAS_PARA_RETIRAR, EstadoReserva
from ..componentes import AZUL, Tabla, boton, campo, desplegable, id_seleccionado, titulo_pantalla


def _disponibles(cantidad: int) -> str:
    return f"{cantidad} disponible{'s' if cantidad != 1 else ''}" if cantidad else "sin disponibles"


class PantallaCatalogoSocio:
    def __init__(self, app):
        self.app = app
        self.libros: dict[int, dict] = {}
        self.sedes_con_copias: list[dict] = []
        self.busqueda = campo("Buscar por título, autor o ISBN", ancho=340, prefix_icon=ft.Icons.SEARCH,
                              on_submit=lambda e: self.refrescar())
        self.tabla_libros = Tabla([("Título", False), ("Autor", False), ("Año", True),
                                   ("Disponibles en la red", True)], self.al_seleccionar_libro,
                                  vacia="No encontramos libros con esa búsqueda.")
        self.tabla_sedes = Tabla([("Sede", False), ("Ejemplares", True), ("Disponibles", True)],
                                 vacia="Seleccione un libro para ver en qué sedes está.")
        self.titulo_detalle = ft.Text("", size=16, weight=ft.FontWeight.BOLD, color=AZUL)
        self.btn_reservar = boton("Reservar", ft.Icons.BOOKMARK_ADD, self.reservar, principal=True,
                                  deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Catálogo", "Busque un libro y consulte en qué sedes puede retirarlo"),
            ft.Row(controls=[self.busqueda, boton("Buscar", ft.Icons.SEARCH, lambda e: self.refrescar())]),
            self.tabla_libros.build(alto=320),
            ft.Row(controls=[self.titulo_detalle, self.btn_reservar],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.tabla_sedes.build(),
        ], spacing=14, expand=True)

    def refrescar(self) -> None:
        filas = self.app.servicios.catalogo.listar_libros(self.busqueda.value or "")
        self.libros = {f["id"]: f for f in filas}
        self.tabla_libros.cargar([(f["id"], [f["titulo"], f["autor"], str(f["anio"] or ""), f["disponibles"]])
                                  for f in filas])
        self.al_seleccionar_libro(self.tabla_libros.seleccionado)

    def al_seleccionar_libro(self, libro_id: int | None) -> None:
        fila = self.libros.get(libro_id)
        self.sedes_con_copias = []
        if fila is not None:
            # Solo sedes activas con copias del libro: son las únicas donde se puede reservar
            self.sedes_con_copias = [d for d in self.app.servicios.catalogo.disponibilidad(libro_id)
                                     if d["activa"] and d["total"]]
        self.titulo_detalle.value = f"«{fila['titulo']}», de {fila['autor']}" if fila else ""
        self.tabla_sedes.cargar([(d["sede_id"], [d["sede"], d["total"], d["disponibles"]])
                                 for d in self.sedes_con_copias])
        if fila is not None and not self.sedes_con_copias:
            self.tabla_sedes.vacia.value = "Ninguna sede tiene copias de este libro."
        self.btn_reservar.disabled = not self.sedes_con_copias

    def reservar(self, e) -> None:
        libro = self.libros[self.tabla_libros.seleccionado]
        sede = desplegable("Sede de retiro", [(d["sede_id"], f"{d['sede']} ({_disponibles(d['disponibles'])})")
                                              for d in self.sedes_con_copias])
        info = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)

        def al_elegir_sede(e=None):
            elegida = next((d for d in self.sedes_con_copias if str(d["sede_id"]) == sede.value), None)
            if elegida is None:
                info.value = "Seleccione la sede donde retirará el libro."
            elif elegida["disponibles"]:
                info.value = (f"Hay un ejemplar disponible: quedará apartado y tendrá {DIAS_PARA_RETIRAR} días "
                              "para retirarlo.")
            else:
                info.value = "Ahora no hay ejemplares libres: su reserva quedará en espera hasta que se libere uno."

        sede.on_select = al_elegir_sede
        al_elegir_sede()

        def guardar():
            reserva = self.app.consulta.reservar(self.app.socio.id, libro["id"],
                                                 id_seleccionado(sede, "la sede de retiro"))
            if reserva.estado == EstadoReserva.ASIGNADA:
                return f"Reserva registrada. Retire el libro antes del {reserva.fecha_expiracion:%d/%m/%Y}."
            return "Reserva registrada. Cuando se libere un ejemplar, figurará como apartado en «Mis reservas»."

        self.app.dialogo(f"Reservar «{libro['titulo']}»", [sede, info], guardar, texto_aceptar="Reservar",
                         ancho=480, al_terminar=self.refrescar)
