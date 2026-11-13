from __future__ import annotations

import flet as ft

from ...modelo.sancion import pesos
from ..componentes import Tabla, mayuscula_inicial, titulo_pantalla
from ..estilo import ERROR, EXITO, LINEA, SUPERFICIE, encabezado


def estado_socio(datos: dict) -> str:
    """Habilitado, Inhabilitado (inhabilitación manual) o Suspendido (por una sanción)."""
    if not datos["bloqueado"]:
        return "Habilitado"
    return "Inhabilitado" if datos["socio"].inhabilitado_manual else "Suspendido"


def _tarjeta(titulo: str, controles: list[ft.Control]) -> ft.Control:
    return ft.Container(
        content=ft.Column(controls=[ft.Text(titulo, size=13, color=ft.Colors.ON_SURFACE_VARIANT), *controles],
                          spacing=6),
        width=360, padding=16, border_radius=10,
        bgcolor=SUPERFICIE, border=ft.Border.all(1, LINEA),
    )


class PantallaSituacionSocio:
    def __init__(self, app):
        self.app = app
        self.estado = encabezado("", size=26)
        self.motivo = ft.Text("", size=13)
        self.prestamos = encabezado("", size=26)
        self.limite = ft.Text("", size=13)
        self.aviso = ft.Container(padding=10, border_radius=6, bgcolor=ERROR[1], visible=False,
                                  content=ft.Text("No puede pedir préstamos ni hacer reservas hasta regularizar "
                                                  "su situación. Consulte en cualquier sede.", color=ERROR[0]))
        self.tabla = Tabla([("Fecha", False), ("Libro", False), ("Días de atraso", True), ("Monto", True)],
                           vacia="No tiene multas impagas.")
        self.total = ft.Text("", weight=ft.FontWeight.BOLD)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Mi situación", "Estado de su cuenta, préstamos abiertos y multas pendientes"),
            ft.Row(controls=[_tarjeta("Estado", [self.estado, self.motivo]),
                             _tarjeta("Préstamos abiertos", [self.prestamos, self.limite])],
                   spacing=16, wrap=True),
            self.aviso,
            ft.Text("Multas impagas", weight=ft.FontWeight.W_600),
            self.tabla.build(alto=260),
            self.total,
        ], spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)

    def refrescar(self) -> None:
        datos = self.app.consulta.situacion(self.app.socio.id)
        socio, bloqueado = datos["socio"], datos["bloqueado"]
        self.estado.value = estado_socio(datos)
        if not bloqueado:
            self.motivo.value = "Puede pedir préstamos y hacer reservas."
        elif socio.inhabilitado_manual:
            self.motivo.value = f"Motivo: {mayuscula_inicial(socio.motivo_inhabilitacion)}."
        else:
            self.motivo.value = f"Está suspendido hasta el {socio.suspendido_hasta:%d/%m/%Y}."
        self.estado.color = ERROR[0] if bloqueado else EXITO[0]
        self.aviso.visible = bloqueado

        abiertos, maximo = datos["prestamos_abiertos"], datos["max_prestamos"]
        self.prestamos.value = f"{abiertos} de {maximo}"
        self.limite.value = ("Alcanzó el máximo: para pedir otro debe devolver uno." if abiertos >= maximo
                             else f"Puede tener hasta {maximo} préstamos abiertos a la vez.")

        self.tabla.cargar([(m["id"], [m["fecha"], m["titulo"], m["dias_atraso"], pesos(m["monto"])])
                           for m in datos["multas_impagas"]])
        self.total.value = f"Total adeudado: {pesos(datos['deuda'])}" if datos["multas_impagas"] else ""
