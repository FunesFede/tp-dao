from __future__ import annotations

import flet as ft

from ...modelo import TipoSancion
from ...modelo.sancion import pesos
from ...reportes.estructura import formatear
from ..componentes import (en_fila, Tabla, boton, campo, desplegable, id_seleccionado, pastilla, texto_o_none,
                           titulo_pantalla)


class PantallaSocios:
    def __init__(self, app):
        self.app = app
        self.filas: dict[int, dict] = {}
        self.busqueda = campo("Buscar por DNI, apellido o nombre", ancho=340, on_submit=lambda e: self.refrescar(),
                              prefix_icon=ft.Icons.SEARCH)
        self.tabla = Tabla([("DNI", False), ("Apellido y nombre", False), ("Sede de alta", False),
                            ("Email", False), ("Teléfono",
                                               False), ("Préstamos abiertos", True), ("Deuda", True),
                            ("Situación", False)], self.al_seleccionar)
        self.btn_editar = boton("Editar", ft.Icons.EDIT,
                                self.editar, deshabilitado=True)
        self.btn_habilitacion = boton("Inhabilitar", ft.Icons.PERSON_OFF, self.cambiar_habilitacion,
                                      deshabilitado=True)
        self.btn_sanciones = boton(
            "Sanciones", ft.Icons.GAVEL, self.ver_sanciones, deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla(
                "Socios", "Alta y modificación de socios, inhabilitaciones y sanciones"),
            ft.Row(controls=[boton("Nuevo socio", ft.Icons.PERSON_ADD, self.nuevo, principal=True), self.btn_editar,
                   self.btn_habilitacion, self.btn_sanciones, ft.Container(expand=True), self.busqueda]),
            self.tabla.build(),
        ], spacing=16, expand=True)

    def refrescar(self) -> None:
        filas = self.app.servicios.socios.listar(self.busqueda.value or "")
        self.filas = {f["id"]: f for f in filas}
        self.tabla.cargar([
            (f["id"], [f["dni"], f"{f['apellido']}, {f['nombre']}", f["sede"], f["email"] or "-",
                       f["telefono"] or "-", f["prestamos_abiertos"], pesos(
                           f["deuda"]) if f["deuda"] else "-",
                       pastilla(f["situacion"])])
            for f in filas
        ])
        self.al_seleccionar(self.tabla.seleccionado)

    def al_seleccionar(self, socio_id: int | None) -> None:
        fila = self.filas.get(socio_id)
        for b in (self.btn_editar, self.btn_habilitacion, self.btn_sanciones):
            b.disabled = fila is None
        self.btn_habilitacion.content = "Habilitar" if fila and fila[
            "inhabilitado_manual"] else "Inhabilitar"

    def _sedes_activas(self):
        return [(s.id, s.nombre) for s in self.app.servicios.sedes.listar(solo_activas=True)]

    def nuevo(self, e) -> None:
        self._formulario(None)

    def editar(self, e) -> None:
        self._formulario(self.filas[self.tabla.seleccionado]["socio"])

    def _formulario(self, socio) -> None:
        dni = campo("DNI", socio.dni if socio else None, ancho=180)
        nombre = campo("Nombre", socio.nombre if socio else None)
        apellido = campo("Apellido", socio.apellido if socio else None)
        email = campo("Email", socio.email if socio else None)
        telefono = campo("Teléfono", socio.telefono if socio else None)
        sedes = self._sedes_activas()
        if socio and socio.sede_id not in [i for i, _ in sedes]:
            sedes.append((socio.sede_id, self.filas[socio.id]["sede"]))
        sede = desplegable("Sede de alta", sedes,
                           socio.sede_id if socio else None)

        def guardar():
            datos = (dni.value, nombre.value, apellido.value,
                     id_seleccionado(sede, "la sede de alta"))
            if socio:
                self.app.servicios.socios.actualizar(
                    socio.id, *datos, texto_o_none(email), texto_o_none(telefono))
                return "Socio actualizado"
            self.app.servicios.socios.crear(
                *datos, texto_o_none(email), texto_o_none(telefono))
            return "Socio creado"

        self.app.dialogo("Editar socio" if socio else "Nuevo socio",
                         [dni, en_fila(nombre, apellido), en_fila(
                             email, telefono), sede],
                         guardar, al_terminar=self.refrescar)

    def cambiar_habilitacion(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        if fila["inhabilitado_manual"]:
            self.app.ejecutar_y_refrescar(self.app.servicios.socios.habilitar, fila["id"], exito="Socio habilitado",
                                          al_terminar=self.refrescar)
            return
        motivo = campo("Motivo", multiline=True, min_lines=2)

        def inhabilitar():
            self.app.servicios.socios.inhabilitar(fila["id"], motivo.value)
            return "Socio inhabilitado"

        self.app.dialogo(f"Inhabilitar a {fila['apellido']}, {fila['nombre']}",
                         [ft.Text(
                             "Mientras esté inhabilitado no podrá pedir préstamos ni reservas."), motivo],
                         inhabilitar, texto_aceptar="Inhabilitar", al_terminar=self.refrescar)

    def ver_sanciones(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        tabla = Tabla([("Fecha", False), ("Libro", False), ("Tipo", False), ("Días de atraso", True),
                       ("Detalle", False), ("Estado", False)], vacia="El socio no tiene sanciones.")
        btn_pagar = boton("Registrar pago", ft.Icons.PAYMENTS, None, deshabilitado=True)

        def cargar():
            sanciones = self.app.servicios.socios.listar_sanciones(fila["id"])
            impagas = {s["id"] for s in sanciones if s["tipo"] == TipoSancion.MONETARIA and not s["pagada"]}
            tabla.cargar([
                (s["id"], [s["fecha"], s["titulo"], "Multa" if s["tipo"] == TipoSancion.MONETARIA else "Suspensión",
                           s["dias_atraso"],
                           pesos(s["monto"]) if s["tipo"] == TipoSancion.MONETARIA
                           else f"Suspendido hasta {formatear(s['suspendido_hasta'])}",
                           pastilla("Pagada", "verde") if s["pagada"] == 1 else
                           pastilla("Impaga", "rojo") if s["tipo"] == TipoSancion.MONETARIA
                           else pastilla("Aplicada", "gris")])
                for s in sanciones])
            btn_pagar.disabled = tabla.seleccionado not in impagas
            tabla.al_seleccionar = lambda i: setattr(btn_pagar, "disabled", i not in impagas)

        tabla.al_seleccionar = lambda i: None
        cargar()
        # El aviso del pago se muestra dentro del diálogo (un SnackBar quedaría tapado por el modal)
        ejecutar = self.app.mostrar_detalle(f"Sanciones de {fila['apellido']}, {fila['nombre']}",
                                            [btn_pagar, tabla.build(alto=320)], ancho=820)
        btn_pagar.on_click = lambda e: ejecutar(self.app.servicios.socios.pagar_multa, tabla.seleccionado,
                                                exito="Pago registrado",
                                                al_terminar=lambda: (cargar(), self.refrescar()))
