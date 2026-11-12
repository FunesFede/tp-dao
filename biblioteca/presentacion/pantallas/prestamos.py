from __future__ import annotations

import flet as ft

from ...modelo import DIAS_PLAZO, EstadoFisico, EstadoPrestamo, TipoPrestamo
from ...reportes.estructura import formatear
from ..componentes import (en_fila, Tabla, boton, campo, desplegable, id_seleccionado, opciones, pastilla, texto_o_none,
                           titulo_pantalla)
from ..estilo import AVISO, ERROR, EXITO

FILTROS = {
    "abiertos": ("Abiertos", EstadoPrestamo.ABIERTOS),
    "vencidos": ("Vencidos", (EstadoPrestamo.VENCIDO,)),
    "retirar": ("Listos para retirar", (EstadoPrestamo.LISTO_PARA_RETIRO,)),
    "viaje": ("Esperando envío o viajando", (EstadoPrestamo.SOLICITADO, EstadoPrestamo.EN_TRANSITO)),
    "cerrados": ("Devueltos y cancelados", (EstadoPrestamo.DEVUELTO, EstadoPrestamo.CANCELADO)),
    "todos": ("Todos", None),
}


class PantallaPrestamos:
    def __init__(self, app):
        self.app = app
        self.filas: dict[int, dict] = {}
        self.filtro = desplegable("Mostrar", [(k, v[0]) for k, v in FILTROS.items()], "abiertos", ancho=270,
                                  al_cambiar=lambda e: self.refrescar())
        self.busqueda = campo("Buscar socio, DNI, libro o código", ancho=360, prefix_icon=ft.Icons.SEARCH,
                              on_submit=lambda e: self.refrescar())
        self.tabla = Tabla([("#", True), ("Tipo", False), ("Socio", False), ("Libro", False), ("Código", False),
                            ("Origen", False), ("Retira en", False), ("Estado", False), ("Vence", False),
                            ("Atraso (días)", True)], self.al_seleccionar)
        self.btn_entregar = boton("Entregar al socio", ft.Icons.HANDSHAKE, self.entregar, deshabilitado=True)
        self.btn_devolver = boton("Registrar devolución", ft.Icons.ASSIGNMENT_RETURN, self.devolver,
                                  deshabilitado=True)
        self.btn_cancelar = boton("Cancelar", ft.Icons.CANCEL_OUTLINED, self.cancelar, deshabilitado=True)
        self.btn_ver_devolucion = boton("Ver devolución", ft.Icons.RECEIPT_LONG, self.ver_devolucion,
                                        deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Préstamos y devoluciones",
                            f"Locales ({DIAS_PLAZO[TipoPrestamo.LOCAL]} días) e interbibliotecarios "
                            f"({DIAS_PLAZO[TipoPrestamo.INTER]} días, con envío entre sedes)"),
            ft.Row(controls=[boton("Nuevo préstamo", ft.Icons.ADD, self.nuevo, principal=True),
                             self.btn_entregar, self.btn_devolver, self.btn_cancelar, self.btn_ver_devolucion]),
            ft.Row(controls=[self.filtro, self.busqueda]),
            self.tabla.build(),
        ], spacing=16, expand=True)

    def refrescar(self) -> None:
        estados = FILTROS[self.filtro.value or "abiertos"][1]
        filas = self.app.servicios.prestamos.listar(estados, self.busqueda.value or "")
        self.filas = {f["id"]: f for f in filas}
        self.tabla.cargar([
            (f["id"], [f["id"], "Inter" if f["tipo"] == TipoPrestamo.INTER else "Local", f["socio"], f["titulo"],
                       f["codigo_inventario"], f["sede_origen"], f["sede_destino"], pastilla(f["estado"]),
                       f["fecha_vencimiento"], f["dias_atraso"] or ""])
            for f in filas])
        self.al_seleccionar(self.tabla.seleccionado)

    def al_seleccionar(self, prestamo_id: int | None) -> None:
        estado = self.filas[prestamo_id]["estado"] if prestamo_id in self.filas else None
        self.btn_entregar.disabled = estado != EstadoPrestamo.LISTO_PARA_RETIRO
        self.btn_devolver.disabled = estado not in (EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO)
        self.btn_cancelar.disabled = estado not in (EstadoPrestamo.SOLICITADO, EstadoPrestamo.LISTO_PARA_RETIRO)
        self.btn_ver_devolucion.disabled = estado != EstadoPrestamo.DEVUELTO

    # --- nuevo préstamo -------------------------------------------------------
    def nuevo(self, e) -> None:
        servicios = self.app.servicios
        sedes = [(s.id, s.nombre) for s in servicios.sedes.listar(solo_activas=True)]
        socios = [(f["id"], f"{f['apellido']}, {f['nombre']} · DNI {f['dni']}"
                   + ("" if f["situacion"] == "habilitado" else f" ({f['situacion']})"))
                  for f in servicios.socios.listar()]
        libros = [(f["id"], f"{f['titulo']} ({f['autor']})") for f in servicios.catalogo.listar_libros()]

        socio = desplegable("Socio", socios, filtrable=True)
        libro = desplegable("Libro", libros, filtrable=True)
        origen = desplegable("Sede de origen", [])
        ejemplar = desplegable("Ejemplar disponible", [])
        destino = desplegable("Sede donde lo retira", sedes)
        info = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)

        def al_elegir_libro(e=None):
            """La sede de origen solo ofrece las sedes activas con ejemplares disponibles del libro."""
            con_stock = [d for d in servicios.catalogo.disponibilidad(int(libro.value))
                         if d["activa"] and d["disponibles"]] if libro.value else []
            origen.options = opciones([
                (d["sede_id"], f"{d['sede']} ({d['disponibles']} disponible{'s' if d['disponibles'] > 1 else ''})")
                for d in con_stock])
            if origen.value not in [str(d["sede_id"]) for d in con_stock]:
                origen.value = str(con_stock[0]["sede_id"]) if len(con_stock) == 1 else None
            origen.disabled = not con_stock
            origen.hint_text = ("Elija primero un libro" if not libro.value else
                                None if con_stock else "Sin ejemplares disponibles")
            actualizar()

        def actualizar(e=None):
            prestables = (servicios.catalogo.listar_ejemplares(int(libro.value), int(origen.value),
                                                               solo_prestables=True)
                          if libro.value and origen.value else [])
            ejemplar.options = opciones([(x["id"], x["codigo_inventario"]) for x in prestables])
            if ejemplar.value not in [str(x["id"]) for x in prestables]:
                ejemplar.value = str(prestables[0]["id"]) if prestables else None
            ejemplar.disabled = not prestables
            if origen.value and not destino.value:
                destino.value = origen.value
            destino.disabled = not origen.value

            if libro.value and origen.disabled:
                info.value = "No hay ejemplares disponibles de este libro en ninguna sede."
                info.color = ERROR[0]
            elif origen.value and destino.value:
                info.color = ft.Colors.ON_SURFACE_VARIANT
                info.value = (f"Préstamo local: el socio se lo lleva ahora, vence en {DIAS_PLAZO['LOCAL']} días."
                              if origen.value == destino.value else
                              "Préstamo interbibliotecario: el ejemplar se agrega a un remito hacia la sede de "
                              f"retiro; vence {DIAS_PLAZO['INTER']} días después de que el socio lo retire.")
            else:
                info.value = ""

        libro.on_select = al_elegir_libro
        origen.on_select = destino.on_select = actualizar
        al_elegir_libro()

        def guardar():
            prestamo = servicios.prestamos.registrar(
                id_seleccionado(socio, "el socio"), id_seleccionado(ejemplar, "un ejemplar disponible"),
                id_seleccionado(origen, "la sede de origen"), id_seleccionado(destino, "la sede de retiro"))
            if prestamo.tipo == TipoPrestamo.LOCAL:
                return f"Préstamo #{prestamo.id} registrado. Vence el {prestamo.fecha_vencimiento:%d/%m/%Y}."
            return f"Préstamo interbibliotecario #{prestamo.id} registrado. El ejemplar se agregó a un remito."

        self.app.dialogo("Nuevo préstamo", [socio, libro, en_fila(origen, destino), ejemplar, info],
                         guardar, texto_aceptar="Registrar préstamo", ancho=620, al_terminar=self.refrescar)

    # --- acciones sobre el seleccionado -------------------------------------
    def entregar(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]

        def entregar():
            prestamo = self.app.servicios.prestamos.entregar(fila["id"])
            return f"Entregado a {fila['socio']}. Vence el {prestamo.fecha_vencimiento:%d/%m/%Y}."

        self.app.confirmar("Entregar préstamo",
                           f"¿{fila['socio']} retira «{fila['titulo']}» en {fila['sede_destino']}?",
                           entregar, al_terminar=self.refrescar)

    def cancelar(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        self.app.confirmar("Cancelar préstamo",
                           f"Se cancela el préstamo de «{fila['titulo']}» a {fila['socio']} y se libera el ejemplar.",
                           lambda: self.app.servicios.prestamos.cancelar(fila["id"]), al_terminar=self.refrescar)

    def devolver(self, e) -> None:
        fila = self.filas[self.tabla.seleccionado]
        sedes = self.app.servicios.sedes.listar()
        recepcion = desplegable("Sede donde se recibe", [(s.id, s.nombre) for s in sedes if s.activa],
                                fila["sede_destino_id"])
        # Se parte del estado que el ejemplar tenía al prestarse; solo puede quedar igual o empeorar
        actual = fila["estado_fisico_ejemplar"]
        estado = desplegable("Estado físico", [(x, x.capitalize().replace("Daniado", "Dañado"))
                                               for x in EstadoFisico.posibles_desde(actual)], actual)
        observaciones = campo("Observaciones", multiline=True, min_lines=2)
        sancion = self.app.servicios.prestamos.sancion_prevista(fila["id"])
        if sancion:
            aviso = ft.Container(content=ft.Text(f"Devolución con atraso. Corresponde: {sancion}.", color=AVISO[0]),
                                 bgcolor=AVISO[1], padding=10, border_radius=3)
        else:
            aviso = ft.Text("Devolución en término: no corresponde sanción.", color=EXITO[0])

        def guardar():
            resultado = self.app.servicios.prestamos.registrar_devolucion(
                fila["id"], id_seleccionado(recepcion, "la sede de recepción"), estado.value,
                texto_o_none(observaciones))
            return resultado.mensaje()

        self.app.dialogo(f"Devolución de «{fila['titulo']}»",
                         [ft.Text(f"Socio: {fila['socio']} · Ejemplar {fila['codigo_inventario']}"), aviso,
                          en_fila(recepcion, estado), observaciones],
                         guardar, texto_aceptar="Registrar devolución", ancho=560, al_terminar=self.refrescar)

    def ver_devolucion(self, e) -> None:
        datos: dict = {}
        prestamo_id = self.tabla.seleccionado
        if not self.app.ejecutar(lambda: datos.update(self.app.servicios.prestamos.detalle_devolucion(prestamo_id))):
            return
        p, d = datos["prestamo"], datos["devolucion"]
        observaciones = d["observaciones"] or "Sin observaciones"
        secciones = [
            _seccion("Préstamo", [
                ("Socio", p["socio"]),
                ("Libro", p["titulo"]),
                ("Ejemplar", p["codigo_inventario"]),
                ("Tipo", "Interbibliotecario" if p["tipo"] == TipoPrestamo.INTER else "Local"),
                ("Sede de origen", p["sede_origen"]),
                ("Sede de retiro", p["sede_destino"]),
                ("Entregado", formatear(p["fecha_inicio"])),
                ("Vencía", formatear(p["fecha_vencimiento"])),
            ]),
            _seccion("Devolución", [
                ("Fecha", formatear(d["fecha"])),
                ("Recibido en", d["sede_recepcion"]),
                ("Estado físico", pastilla(d["estado_fisico"], "verde" if d["estado_fisico"] == "BUENO" else None)),
                ("Días de atraso", str(d["dias_atraso"]) if d["dias_atraso"] else "Sin atraso"),
                ("Observaciones", ft.Text(observaciones, selectable=True, italic=not d["observaciones"])),
            ]),
        ]
        sanciones = [ft.Row(controls=[ft.Text(s["descripcion"], expand=True)]
                            + ([] if s["pagada"] is None   # una suspensión no se paga
                               else [pastilla("Pagada", "verde") if s["pagada"] else pastilla("Impaga", "rojo")]))
                     for s in datos["sanciones"]]
        secciones.append(_seccion("Sanción", sanciones or [ft.Text("Devuelto en término, sin sanción")]))
        self.app.mostrar_detalle(f"Devolución de «{p['titulo']}»", secciones, ancho=580)


def _seccion(titulo: str, pares: list) -> ft.Control:
    """Título de sección y sus filas: pares (etiqueta, valor) o controles ya armados."""
    filas = []
    for par in pares:
        if isinstance(par, ft.Control):
            filas.append(par)
            continue
        etiqueta, valor = par
        control = valor if isinstance(valor, ft.Control) else ft.Text(str(valor))
        filas.append(ft.Row(controls=[
            ft.Text(etiqueta, color=ft.Colors.ON_SURFACE_VARIANT, width=130),
            ft.Container(content=control, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START))
    return ft.Column(controls=[ft.Text(titulo, weight=ft.FontWeight.BOLD, size=15), *filas], spacing=6)
