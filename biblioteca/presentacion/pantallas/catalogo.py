from __future__ import annotations

import flet as ft

from ...modelo import EstadoFisico, TipoMaterial
from ..componentes import (en_fila, Tabla, boton, campo, desplegable, entero_o_none, id_seleccionado, pastilla,
                           texto_o_none, titulo_pantalla)
from ..estilo import encabezado


class PantallaCatalogo:
    def __init__(self, app):
        self.app = app
        self.libros: dict[int, dict] = {}
        self.ejemplares: dict[int, dict] = {}
        self.busqueda = campo("Buscar por título, autor o ISBN", ancho=340, prefix_icon=ft.Icons.SEARCH,
                              on_submit=lambda e: self.refrescar())
        self.tabla_libros = Tabla([("Título", False), ("Autor", False), ("ISBN", False), ("Año", True),
                                   ("Tipo", False), ("Ejemplares", True), ("Disponibles", True),
                                   ("De baja", True)],
                                  self.al_seleccionar_libro)
        self.tabla_disponibilidad = Tabla([("Sede", False), ("Ejemplares", True), ("Disponibles", True),
                                           ("Prestados", True), ("Apartados", True), ("Fuera de su sede", True)],
                                          vacia="Seleccione un libro.")
        self.tabla_ejemplares = Tabla([("Código", False), ("Sede", False), ("Ubicación actual", False),
                                       ("Estado", False), ("Estado físico", False)], self.al_seleccionar_ejemplar,
                                      vacia="Seleccione un libro.")
        self.titulo_detalle = encabezado("", size=18)
        self.btn_editar = boton("Editar libro", ft.Icons.EDIT, self.editar_libro, deshabilitado=True)
        self.btn_ejemplar = boton("Agregar ejemplar", ft.Icons.ADD_BOX, self.agregar_ejemplar, deshabilitado=True)
        self.btn_baja = boton("Dar de baja", ft.Icons.DELETE_OUTLINE, self.dar_de_baja, deshabilitado=True)
        self.btn_reparar = boton("Registrar reparación", ft.Icons.BUILD_OUTLINED, self.reparar, deshabilitado=True)
        self.btn_retorno = boton("Enviar a su sede", ft.Icons.KEYBOARD_RETURN, self.enviar_a_su_sede,
                                 deshabilitado=True)

    def build(self) -> ft.Control:
        return ft.Column(controls=[
            titulo_pantalla("Catálogo", "Libros, ejemplares físicos por sede y consulta de disponibilidad"),
            ft.Row(controls=[boton("Nuevo libro", ft.Icons.ADD, self.nuevo_libro, principal=True),
                             self.btn_editar, self.btn_ejemplar, ft.Container(expand=True), self.busqueda]),
            self.tabla_libros.build(alto=300),
            self.titulo_detalle,
            ft.Row(controls=[
                ft.Column(controls=[ft.Text("Disponibilidad en la red", weight=ft.FontWeight.W_600),
                                    self.tabla_disponibilidad.build()], expand=5),
                ft.Column(controls=[
                    # Los botones van en su propia fila con wrap: un control con expand no puede estar
                    # dentro de una fila con wrap (Flutter no la dibuja)
                    ft.Row(controls=[
                        ft.Text("Ejemplares", weight=ft.FontWeight.W_600),
                        ft.Row(controls=[self.btn_reparar, self.btn_retorno, self.btn_baja], wrap=True,
                               alignment=ft.MainAxisAlignment.END, expand=True),
                    ], vertical_alignment=ft.CrossAxisAlignment.START),
                    self.tabla_ejemplares.build()], expand=6),
            ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START, spacing=20),
        ], spacing=14, expand=True)

    def refrescar(self) -> None:
        filas = self.app.servicios.catalogo.listar_libros(self.busqueda.value or "")
        self.libros = {f["id"]: f for f in filas}
        self.tabla_libros.cargar([
            (f["id"], [f["titulo"], f["autor"], f["isbn"], str(f["anio"] or ""), f["tipo_material"].capitalize(),
                       f["ejemplares"], f["disponibles"], f["bajas"]]) for f in filas])
        self.al_seleccionar_libro(self.tabla_libros.seleccionado)

    def al_seleccionar_libro(self, libro_id: int | None) -> None:
        fila = self.libros.get(libro_id)
        self.btn_editar.disabled = self.btn_ejemplar.disabled = fila is None
        if fila is None:
            self.titulo_detalle.value = ""
            self.tabla_disponibilidad.cargar([])
            self.tabla_ejemplares.cargar([])
            self.ejemplares = {}
        else:
            self.titulo_detalle.value = f"«{fila['titulo']}», de {fila['autor']}"
            disponibilidad = self.app.servicios.catalogo.disponibilidad(libro_id)
            self.tabla_disponibilidad.cargar([
                (d["sede_id"], [d["sede"] + ("" if d["activa"] else " (baja)"), d["total"], d["disponibles"],
                                d["prestados"], d["reservados"], d["fuera_de_sede"]])
                for d in disponibilidad if d["total"]])
            ejemplares = self.app.servicios.catalogo.listar_ejemplares(libro_id)
            self.ejemplares = {e["id"]: e for e in ejemplares}
            self.tabla_ejemplares.cargar([
                (e["id"], [e["codigo_inventario"], e["sede"],
                           e["sede_actual"] if e["sede_actual_id"] != e["sede_id"] else "En su sede",
                           self._estado_ejemplar(e),
                           pastilla(e["estado_fisico"], "verde" if e["estado_fisico"] == "BUENO" else None)])
                for e in ejemplares])
        self.al_seleccionar_ejemplar(self.tabla_ejemplares.seleccionado)

    @staticmethod
    def _estado_ejemplar(e: dict) -> ft.Control:
        if e["estado"] == "DISPONIBLE" and not e["sede_activa"]:
            return pastilla("SEDE_DE_BAJA")
        if e["estado"] == "RESERVADO":
            motivo = (f" · préstamo #{e['apartado_prestamo_id']}" if e["apartado_prestamo_id"] else
                      f" · reserva de {e['apartado_reserva_de']}" if e["apartado_reserva_de"] else "")
            return pastilla(f"Apartado{motivo}", "ambar")
        return pastilla(e["estado"])

    def al_seleccionar_ejemplar(self, ejemplar_id: int | None) -> None:
        e = self.ejemplares.get(ejemplar_id)
        self.btn_baja.disabled = e is None or e["estado"] != "DISPONIBLE"
        self.btn_reparar.disabled = (e is None or e["estado"] != "DISPONIBLE"
                                     or not EstadoFisico.mejores_que(e["estado_fisico"]))
        self.btn_retorno.disabled = e is None or e["estado"] != "DISPONIBLE" or e["sede_actual_id"] == e["sede_id"]

    # --- acciones ------------------------------------------------------------
    def nuevo_libro(self, e) -> None:
        self._formulario(None)

    def editar_libro(self, e) -> None:
        self._formulario(self.libros[self.tabla_libros.seleccionado]["libro"])

    def _formulario(self, libro) -> None:
        isbn = campo("ISBN", libro.isbn if libro else None, ancho=220)
        titulo = campo("Título", libro.titulo if libro else None)
        autor = campo("Autor", libro.autor if libro else None)
        editorial = campo("Editorial", libro.editorial if libro else None)
        anio = campo("Año", libro.anio if libro else None, ancho=110)
        tipo = desplegable("Tipo de material", [(t, t.capitalize()) for t in TipoMaterial.TODOS],
                           libro.tipo_material if libro else "LIBRO", ancho=200)

        def guardar():
            datos = (isbn.value, titulo.value, autor.value, texto_o_none(editorial), entero_o_none(anio, "El año"),
                     tipo.value)
            if libro:
                self.app.servicios.catalogo.actualizar_libro(libro.id, *datos)
                return "Libro actualizado"
            self.app.servicios.catalogo.crear_libro(*datos)
            return "Libro creado. Agregue sus ejemplares desde «Agregar ejemplar»."

        self.app.dialogo("Editar libro" if libro else "Nuevo libro",
                         [en_fila(isbn, tipo), titulo, autor, en_fila(editorial, anio)],
                         guardar, al_terminar=self.refrescar)

    def agregar_ejemplar(self, e) -> None:
        libro = self.libros[self.tabla_libros.seleccionado]
        sedes = [(s.id, s.nombre) for s in self.app.servicios.sedes.listar(solo_activas=True)]
        sede = desplegable("Sede propietaria", sedes)
        codigo = campo("Código de inventario", hint_text="Vacío para generarlo automáticamente")

        def guardar():
            ejemplar = self.app.servicios.catalogo.agregar_ejemplar(
                libro["id"], id_seleccionado(sede, "la sede"), texto_o_none(codigo))
            return f"Ejemplar {ejemplar.codigo_inventario} agregado"

        self.app.dialogo(f"Agregar ejemplar de «{libro['titulo']}»", [sede, codigo], guardar,
                         al_terminar=self.refrescar)

    def dar_de_baja(self, e) -> None:
        ejemplar = self.ejemplares[self.tabla_ejemplares.seleccionado]

        def baja():
            self.app.servicios.catalogo.dar_de_baja_ejemplar(ejemplar["id"])
            return f"Ejemplar {ejemplar['codigo_inventario']} dado de baja"

        self.app.confirmar("Dar de baja el ejemplar",
                           f"El ejemplar {ejemplar['codigo_inventario']} dejará de estar disponible para préstamos.",
                           baja, al_terminar=self.refrescar)

    def reparar(self, e) -> None:
        ejemplar = self.ejemplares[self.tabla_ejemplares.seleccionado]
        estado = desplegable("Nuevo estado físico",
                             [(x, x.capitalize().replace("Daniado", "Dañado"))
                              for x in EstadoFisico.mejores_que(ejemplar["estado_fisico"])], EstadoFisico.BUENO)

        def guardar():
            self.app.servicios.catalogo.reparar_ejemplar(ejemplar["id"], estado.value)
            return f"Ejemplar {ejemplar['codigo_inventario']} reparado"

        actual = ejemplar["estado_fisico"].capitalize().replace("Daniado", "Dañado")
        self.app.dialogo(f"Reparación de {ejemplar['codigo_inventario']}",
                         [ft.Text(f"Estado actual: {actual}. Elija cómo quedó el ejemplar después de repararlo."),
                          estado], guardar, texto_aceptar="Registrar reparación", ancho=440,
                         al_terminar=self.refrescar)

    def enviar_a_su_sede(self, e) -> None:
        self.app.ejecutar_y_refrescar(self.app.servicios.catalogo.enviar_a_su_sede,
                                      self.tabla_ejemplares.seleccionado, al_terminar=self.refrescar)
