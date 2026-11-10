from __future__ import annotations

import flet as ft

from ...modelo import PoliticaSancion, Sede
from ...modelo.sancion import pesos
from ..componentes import (en_fila, Tabla, boton, campo, desplegable, numero_o_none, pastilla, texto_o_none,
                           titulo_pantalla)


class PantallaSedes:
    def __init__(self, app):
        self.app = app
        self.sedes: dict[int, Sede] = {}
        self.tabla = Tabla([("Nombre", False), ("Dirección", False), ("Teléfono", False), ("Horario", False),
                            ("Política de sanción", False), ("Estado", False)], self.al_seleccionar)
        self.btn_editar = boton("Editar", ft.Icons.EDIT, self.editar, deshabilitado=True)
        self.btn_baja = boton("Dar de baja", ft.Icons.BLOCK, self.cambiar_estado, deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Sedes", "Datos de contacto, horarios, estado y política de sanción por atraso"),
            ft.Row(controls=[boton("Nueva sede", ft.Icons.ADD, self.nueva, principal=True),
                             self.btn_editar, self.btn_baja]),
            self.tabla.build(),
        ], spacing=16, expand=True)

    def refrescar(self) -> None:
        self.sedes = {s.id: s for s in self.app.servicios.sedes.listar()}
        self.tabla.cargar([
            (s.id, [s.nombre, s.direccion, s.telefono, s.horario, self._politica(s),
                    pastilla("ACTIVA" if s.activa else "DADA DE BAJA")])
            for s in self.sedes.values()
        ])
        self.al_seleccionar(self.tabla.seleccionado)

    @staticmethod
    def _politica(sede: Sede) -> str:
        if sede.politica_sancion == PoliticaSancion.MONETARIA:
            return f"Multa: {pesos(sede.monto_por_dia)} por día"
        return f"Suspensión: {sede.factor_suspension} día(s) por día de atraso"

    def al_seleccionar(self, sede_id: int | None) -> None:
        sede = self.sedes.get(sede_id)
        self.btn_editar.disabled = sede is None
        self.btn_baja.disabled = sede is None
        self.btn_baja.content = "Reactivar" if sede and not sede.activa else "Dar de baja"

    def nueva(self, e) -> None:
        self._formulario(None)

    def editar(self, e) -> None:
        self._formulario(self.sedes[self.tabla.seleccionado])

    def _formulario(self, sede: Sede | None) -> None:
        nombre = campo("Nombre", sede.nombre if sede else None)
        direccion = campo("Dirección", sede.direccion if sede else None)
        telefono = campo("Teléfono", sede.telefono if sede else None)
        email = campo("Email", sede.email if sede else None)
        horario = campo("Horario de atención", sede.horario if sede else None)
        politica_actual = sede.politica_sancion if sede else PoliticaSancion.MONETARIA
        valor_actual = (sede.monto_por_dia if politica_actual == PoliticaSancion.MONETARIA
                        else sede.factor_suspension) if sede else None
        valor = campo("", valor_actual)

        def actualizar_etiqueta(e=None):
            valor.label = ("Monto por día de atraso ($)" if politica.value == PoliticaSancion.MONETARIA
                           else "Días de suspensión por cada día de atraso")

        politica = desplegable("Política de sanción por atraso",
                               [(PoliticaSancion.MONETARIA, "Multa monetaria"),
                                (PoliticaSancion.SUSPENSION, "Suspensión del socio")],
                               politica_actual, al_cambiar=actualizar_etiqueta)
        actualizar_etiqueta()

        def guardar():
            datos = (nombre.value, direccion.value, texto_o_none(telefono), texto_o_none(email),
                     texto_o_none(horario), politica.value, numero_o_none(valor, "El valor de la sanción"))
            if sede:
                self.app.servicios.sedes.actualizar(sede.id, *datos)
                return "Sede actualizada"
            self.app.servicios.sedes.crear(*datos)
            return "Sede creada"

        self.app.dialogo("Editar sede" if sede else "Nueva sede",
                         [nombre, direccion, en_fila(telefono, email), horario,
                          ft.Text("La política se aplica a los préstamos cuyo ejemplar pertenece a esta sede.",
                                  size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                          politica, valor],
                         guardar, al_terminar=self.refrescar)

    def cambiar_estado(self, e) -> None:
        sede = self.sedes[self.tabla.seleccionado]
        if sede.activa:
            def dar_de_baja():
                self.app.servicios.sedes.dar_de_baja(sede.id)
                return "Sede dada de baja"

            self.app.confirmar("Dar de baja la sede",
                               f"«{sede.nombre}» no podrá recibir préstamos, reservas ni envíos nuevos. "
                               "Sus datos y su historial se conservan.",
                               dar_de_baja, al_terminar=self.refrescar)
        else:
            self.app.ejecutar_y_refrescar(self.app.servicios.sedes.reactivar, sede.id, exito="Sede reactivada",
                                          al_terminar=self.refrescar)
