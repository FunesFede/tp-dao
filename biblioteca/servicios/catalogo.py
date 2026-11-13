from __future__ import annotations

from ..modelo import Ejemplar, ErrorNegocio, Libro
from .base import ServicioBase
from .operaciones import asignar_reservas, empaquetar, quitar_de_remito_en_preparacion


class ServicioCatalogo(ServicioBase):
    # --- libros --------------------------------------------------------------
    def listar_libros(self, texto: str = "") -> list[dict]:
        with self._transaccion() as r:
            return r.libros.listar_resumen(texto)

    def crear_libro(self, isbn: str, titulo: str, autor: str, editorial: str | None = None,
                    anio: int | None = None, tipo_material: str = "LIBRO") -> Libro:
        libro = Libro(isbn=isbn, titulo=titulo, autor=autor, editorial=editorial or None,
                      anio=anio, tipo_material=tipo_material)
        with self._transaccion() as r:
            r.libros.crear(libro)
        return libro

    def actualizar_libro(self, libro_id: int, isbn: str, titulo: str, autor: str,
                         editorial: str | None, anio: int | None, tipo_material: str) -> Libro:
        libro = Libro(isbn=isbn, titulo=titulo, autor=autor, editorial=editorial or None,
                      anio=anio, tipo_material=tipo_material, id=libro_id)
        with self._transaccion() as r:
            self._obtener(r.libros.obtener_por_id(libro_id), "el libro")
            r.libros.actualizar(libro)
        return libro

    # --- ejemplares ----------------------------------------------------------
    def listar_ejemplares(self, libro_id: int | None = None, sede_id: int | None = None,
                          solo_prestables: bool = False) -> list[dict]:
        with self._transaccion() as r:
            return r.ejemplares.listar_resumen(libro_id, sede_id, solo_prestables)

    def agregar_ejemplar(self, libro_id: int, sede_id: int, codigo_inventario: str | None = None) -> Ejemplar:
        with self._transaccion() as r:
            self._obtener(r.libros.obtener_por_id(libro_id), "el libro")
            sede = self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")
            sede.exigir_activa()
            codigo = (codigo_inventario or "").strip().upper()
            if not codigo:
                numero = r.ejemplares.siguiente_numero(libro_id, sede_id)
                codigo = f"S{sede_id:02d}-L{libro_id:04d}-{numero:03d}"
            ejemplar = Ejemplar(libro_id=libro_id, sede_id=sede_id, sede_actual_id=sede_id,
                                codigo_inventario=codigo)
            r.ejemplares.crear(ejemplar)
            asignar_reservas(r, libro_id, sede_id, self.ahora().date())
        return ejemplar

    def dar_de_baja_ejemplar(self, ejemplar_id: int) -> str:
        with self._transaccion() as r:
            ejemplar = self._obtener(r.ejemplares.obtener_por_id(ejemplar_id), "el ejemplar")
            ejemplar.dar_de_baja()
            r.ejemplares.actualizar(ejemplar)
            # Si esperaba en un remito de retorno, ya no viaja
            numero = quitar_de_remito_en_preparacion(
                r, ejemplar.id, f"Anulado al dar de baja el ejemplar {ejemplar.codigo_inventario}", self.reloj)
            mensaje = f"Ejemplar {ejemplar.codigo_inventario} dado de baja"
            return mensaje + (f" y quitado del remito {numero}" if numero else "")

    def reparar_ejemplar(self, ejemplar_id: int, estado_fisico: str) -> None:
        with self._transaccion() as r:
            ejemplar = self._obtener(r.ejemplares.obtener_por_id(ejemplar_id), "el ejemplar")
            ejemplar.reparar(estado_fisico)
            r.ejemplares.actualizar(ejemplar)

    def enviar_a_su_sede(self, ejemplar_id: int) -> str:
        """Empaqueta un ejemplar disponible que quedó fuera de su sede en un remito de retorno."""
        with self._transaccion() as r:
            ejemplar = self._obtener(r.ejemplares.obtener_por_id(ejemplar_id), "el ejemplar")
            if ejemplar.esta_en_su_sede():
                raise ErrorNegocio("El ejemplar ya está en su sede")
            if not ejemplar.esta_disponible():
                raise ErrorNegocio(f"El ejemplar está {ejemplar.estado}; solo se envían ejemplares disponibles")
            remito = empaquetar(r, ejemplar, None, ejemplar.sede_actual_id, ejemplar.sede_id, self.reloj)
            return f"Ejemplar agregado al remito {remito.numero}"

    def libros_de_sede(self, sede_id: int) -> list[dict]:
        """Títulos que la sede tiene en su catálogo: son los que se pueden reservar en ella."""
        with self._transaccion() as r:
            self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")
            return r.ejemplares.libros_de_sede(sede_id)

    def disponibilidad(self, libro_id: int) -> list[dict]:
        """Consulta de disponibilidad de un título en cada sede de la red."""
        with self._transaccion() as r:
            self._obtener(r.libros.obtener_por_id(libro_id), "el libro")
            return r.ejemplares.disponibilidad_por_sede(libro_id)
