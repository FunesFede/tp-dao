from __future__ import annotations

import flet as ft

from ...modelo import ResultadoRecepcion
from ...reportes.estructura import formatear
from ..componentes import Tabla, boton, campo, desplegable, etiqueta_estado, pastilla, titulo_pantalla
from ..estilo import ACENTO, encabezado

ACCIONES_POR_ESTADO = {
    "EN_PREPARACION": {"despachar", "anular"},
    "DESPACHADO": {"transito", "recibir", "extravio"},
    "EN_TRANSITO": {"transito", "recibir", "extravio"},
}


class PantallaRemitos:
    def __init__(self, app):
        self.app = app
        self.filas: dict[int, dict] = {}
        self.detalle: dict | None = None
        self.solo_en_curso = ft.Switch(label="Solo en curso", value=False, on_change=lambda e: self.refrescar())
        self.tabla = Tabla([("Número", False), ("Origen", False), ("Destino", False), ("Ejemplares", True),
                            ("Estado", False), ("Último mov.", False)], self.al_seleccionar)
        self.tabla_ejemplares = Tabla([("Código", False), ("Libro", False), ("Motivo", False),
                                       ("Recepción", False)], vacia="Sin ejemplares para mostrar")
        self.historial = ft.Column(spacing=0)
        self.cabecera = encabezado("Seleccione un remito para ver su detalle", size=18)
        self.transito = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.botones = {
            "despachar": boton("Despachar", ft.Icons.OUTBOX, self.despachar, principal=True),
            "transito": boton("Registrar tránsito", ft.Icons.ROUTE, self.registrar_transito),
            "recibir": boton("Recibir", ft.Icons.MOVE_TO_INBOX, self.recibir, principal=True),
            "extravio": boton("Declarar extravío", ft.Icons.REPORT_PROBLEM, self.declarar_extravio),
            "anular": boton("Anular", ft.Icons.CANCEL_OUTLINED, self.anular),
        }

    def build(self) -> ft.Control:
        detalle = ft.Container(
            content=ft.Column(controls=[
                self.cabecera, self.transito,
                ft.Row(controls=list(self.botones.values()), wrap=True),
                ft.Text("Ejemplares", weight=ft.FontWeight.W_600),
                self.tabla_ejemplares.build(alto=200),
                ft.Text("Trazabilidad", weight=ft.FontWeight.W_600),
                ft.Container(content=self.historial, expand=True),
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
            expand=5, padding=ft.Padding.only(left=8),
        )
        return ft.Column(controls=[
            titulo_pantalla("Remitos", "Empaquetado, despacho, tránsito y recepción de ejemplares entre sedes"),
            ft.Text("Los remitos son generados automáticamente al registrar un préstamo interbibliotecario o al "
                    "devolver un ejemplar a su sede de origen.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            self.solo_en_curso,
            ft.Row(controls=[ft.Column(controls=[self.tabla.build()], expand=7), detalle], expand=True,
                   vertical_alignment=ft.CrossAxisAlignment.START, spacing=20),
        ], spacing=12, expand=True)

    def refrescar(self) -> None:
        filas = self.app.servicios.remitos.listar(self.solo_en_curso.value)
        self.filas = {f["id"]: f for f in filas}
        self.tabla.cargar([
            (f["id"], [f["numero"], f["sede_origen"], f["sede_destino"], f["ejemplares"], pastilla(f["estado"]),
                       f["ultimo_movimiento"]]) for f in filas])
        self.al_seleccionar(self.tabla.seleccionado)

    def al_seleccionar(self, remito_id: int | None) -> None:
        self.detalle = self.app.servicios.remitos.detalle(remito_id) if remito_id else None
        permitidas = set()
        if self.detalle is None:
            self.cabecera.value = "Seleccione un remito para ver su detalle"
            self.transito.value = ""
            self.tabla_ejemplares.cargar([])
            self.historial.controls = []
        else:
            remito = self.detalle["remito"]
            fila = self.filas[remito_id]
            permitidas = ACCIONES_POR_ESTADO.get(remito.estado, set())
            self.cabecera.value = f"{remito.numero}: {fila['sede_origen']} → {fila['sede_destino']}"
            horas = self.detalle["tiempo_en_transito"]
            self.transito.value = (f"Tiempo en tránsito: {horas.total_seconds() / 3600:.1f} h" if horas
                                   else f"Creado el {formatear(str(remito.fecha_creacion))}")
            self.tabla_ejemplares.cargar([
                (e["ejemplar_id"], [e["codigo_inventario"], e["titulo"],
                                    f"Préstamo de {e['socio']}" if e["prestamo_id"] else "Retorno a su sede",
                                    pastilla(e["estado_recepcion"]) if e["estado_recepcion"] else "-"])
                for e in self.detalle["ejemplares"]])
            self.historial.controls = [self._hito(m, i == len(self.detalle["movimientos"]) - 1)
                                       for i, m in enumerate(self.detalle["movimientos"])]
        for clave, b in self.botones.items():
            b.visible = clave in permitidas

    @staticmethod
    def _hito(m: dict, ultimo: bool) -> ft.Control:
        return ft.Row(controls=[
            ft.Column(controls=[
                ft.Container(width=12, height=12, border_radius=6, bgcolor=ACENTO),
                ft.Container(width=2, height=34, bgcolor=ft.Colors.OUTLINE_VARIANT, visible=not ultimo),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column(controls=[
                ft.Row(controls=[ft.Text(formatear(m["fecha_hora"]), weight=ft.FontWeight.W_600, size=13),
                                 pastilla(m["estado_nuevo"])], spacing=8),
                ft.Text(" · ".join(x for x in (m["sede"], m["observacion"]) if x), size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=2),
        ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=10)

    # --- acciones (cada estado del remito decide si la admite) --------------
    def _numero(self) -> str:
        return self.detalle["remito"].numero

    def despachar(self, e) -> None:
        self.app.ejecutar_y_refrescar(self.app.servicios.remitos.despachar, self.tabla.seleccionado,
                                      al_terminar=self.refrescar)

    def registrar_transito(self, e) -> None:
        observacion = campo("Observación", hint_text="Ej.: Centro de distribución")
        self.app.dialogo(f"Registrar tránsito de {self._numero()}", [observacion],
                         lambda: self.app.servicios.remitos.registrar_transito(self.tabla.seleccionado,
                                                                               observacion.value),
                         texto_aceptar="Registrar", al_terminar=self.refrescar)

    def recibir(self, e) -> None:
        resultados = {}
        filas = []
        for ej in self.detalle["ejemplares"]:
            resultados[ej["ejemplar_id"]] = desplegable(
                "Resultado", [(r, etiqueta_estado(r)) for r in ResultadoRecepcion.TODOS],
                ResultadoRecepcion.OK, ancho=230)
            filas.append(ft.Row(controls=[
                ft.Column(controls=[ft.Text(ej["titulo"], weight=ft.FontWeight.W_500),
                                    ft.Text(ej["codigo_inventario"], size=12, color=ft.Colors.ON_SURFACE_VARIANT)],
                          spacing=0, expand=True),
                resultados[ej["ejemplar_id"]]]))

        def guardar():
            incidencias = {i: d.value for i, d in resultados.items() if d.value != ResultadoRecepcion.OK}
            return self.app.servicios.remitos.recibir(self.tabla.seleccionado, incidencias)

        self.app.dialogo(f"Recepción de {self._numero()}",
                         [ft.Text("¡Revise el estado de cada ejemplar al abrir el paquete!")] + filas,
                         guardar, texto_aceptar="Confirmar recepción", ancho=600, al_terminar=self.refrescar)

    def declarar_extravio(self, e) -> None:
        observacion = campo("Detalle", multiline=True, min_lines=2)
        self.app.dialogo(f"Declarar extraviado {self._numero()}",
                         [ft.Text("Todos los ejemplares del remito quedarán como EXTRAVIADOS y los préstamos "
                                  "asociados se cancelarán."), observacion],
                         lambda: self.app.servicios.remitos.declarar_extravio(self.tabla.seleccionado,
                                                                              observacion.value),
                         texto_aceptar="Declarar extravío", al_terminar=self.refrescar)

    def anular(self, e) -> None:
        motivo = campo("Motivo")
        self.app.dialogo(f"Anular {self._numero()}",
                         [ft.Text("Los préstamos asociados se cancelarán y los ejemplares serán liberados."), motivo],
                         lambda: self.app.servicios.remitos.anular(self.tabla.seleccionado, motivo.value),
                         texto_aceptar="Anular remito", al_terminar=self.refrescar)
