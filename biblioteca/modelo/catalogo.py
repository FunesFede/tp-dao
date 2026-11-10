"""Libro (la obra del catálogo) y Ejemplar (cada copia física)."""
from __future__ import annotations

from dataclasses import dataclass

from .excepciones import ErrorNegocio


class TipoMaterial:
    TODOS = ("LIBRO", "REVISTA", "MAPA", "MULTIMEDIA", "OTRO")


class EstadoEjemplar:
    DISPONIBLE = "DISPONIBLE"
    RESERVADO = "RESERVADO"      # apartado para una reserva o un préstamo interbibliotecario
    PRESTADO = "PRESTADO"
    EN_TRANSITO = "EN_TRANSITO"
    EXTRAVIADO = "EXTRAVIADO"
    BAJA = "BAJA"
    TODOS = (DISPONIBLE, RESERVADO, PRESTADO, EN_TRANSITO, EXTRAVIADO, BAJA)


class EstadoFisico:
    BUENO = "BUENO"
    REGULAR = "REGULAR"
    DANIADO = "DANIADO"
    DESTRUIDO = "DESTRUIDO"
    TODOS = (BUENO, REGULAR, DANIADO, DESTRUIDO)   # de mejor a peor

    @classmethod
    def posibles_desde(cls, actual: str) -> tuple[str, ...]:
        """Estados que puede tener el material al volver: el mismo o uno peor (devolver no lo repara)."""
        return cls.TODOS[cls.TODOS.index(actual):]

    @classmethod
    def mejores_que(cls, actual: str) -> tuple[str, ...]:
        """Estados a los que puede pasar el material al repararlo (DESTRUIDO no tiene arreglo)."""
        return () if actual == cls.DESTRUIDO else cls.TODOS[:cls.TODOS.index(actual)]


class ResultadoRecepcion:
    OK = "OK"
    DANIADO = "DANIADO"
    FALTANTE = "FALTANTE"
    DESTRUIDO = "DESTRUIDO"
    TODOS = (OK, DANIADO, FALTANTE, DESTRUIDO)
    INCIDENCIAS = (DANIADO, FALTANTE, DESTRUIDO)


@dataclass
class Libro:
    isbn: str
    titulo: str
    autor: str
    editorial: str | None = None
    anio: int | None = None
    tipo_material: str = "LIBRO"
    id: int | None = None

    def __post_init__(self):
        self.isbn = (self.isbn or "").strip().replace("-", "").replace(" ", "").upper()
        self.titulo = (self.titulo or "").strip()
        self.autor = (self.autor or "").strip()
        cuerpo = self.isbn[:-1]
        control = self.isbn[-1:]
        if len(self.isbn) not in (10, 13) or not cuerpo.isdigit() or not (control.isdigit() or control == "X"):
            raise ErrorNegocio("El ISBN debe tener 10 o 13 caracteres numéricos (el último puede ser X)")
        if not self.titulo or not self.autor:
            raise ErrorNegocio("Título y autor son obligatorios")
        if self.anio is not None and not 1400 <= self.anio <= 2100:
            raise ErrorNegocio("El año de edición no es válido")
        if self.tipo_material not in TipoMaterial.TODOS:
            raise ErrorNegocio(f"Tipo de material desconocido: {self.tipo_material}")


@dataclass
class Ejemplar:
    libro_id: int
    sede_id: int            # sede propietaria: no cambia
    sede_actual_id: int     # dónde está físicamente: cambia con cada envío
    codigo_inventario: str
    estado: str = EstadoEjemplar.DISPONIBLE
    estado_fisico: str = EstadoFisico.BUENO
    id: int | None = None

    # --- consultas -----------------------------------------------------------
    def esta_disponible(self) -> bool:
        return self.estado == EstadoEjemplar.DISPONIBLE

    def pertenece_a(self, sede_id: int) -> bool:
        return self.sede_id == sede_id

    def esta_en_su_sede(self) -> bool:
        return self.sede_actual_id == self.sede_id

    # --- transiciones --------------------------------------------------------
    def _exigir(self, estados: tuple[str, ...], accion: str) -> None:
        if self.estado not in estados:
            raise ErrorNegocio(
                f"No se puede {accion} el ejemplar {self.codigo_inventario}: está {self.estado}")

    def apartar(self) -> None:
        self._exigir((EstadoEjemplar.DISPONIBLE,), "apartar")
        self.estado = EstadoEjemplar.RESERVADO

    def liberar(self) -> None:
        self._exigir((EstadoEjemplar.RESERVADO,), "liberar")
        self.estado = EstadoEjemplar.DISPONIBLE

    def prestar(self) -> None:
        self._exigir((EstadoEjemplar.DISPONIBLE, EstadoEjemplar.RESERVADO), "prestar")
        self.estado = EstadoEjemplar.PRESTADO

    def devolver(self, sede_id: int, estado_fisico: str) -> None:
        self._exigir((EstadoEjemplar.PRESTADO,), "devolver")
        if estado_fisico not in EstadoFisico.TODOS:
            raise ErrorNegocio(f"Estado físico desconocido: {estado_fisico}")
        if estado_fisico not in EstadoFisico.posibles_desde(self.estado_fisico):
            raise ErrorNegocio(f"El ejemplar ya estaba en estado {self.estado_fisico}; "
                               "al devolverlo su estado físico no puede mejorar")
        self.sede_actual_id = sede_id
        self.estado_fisico = estado_fisico
        self.estado = EstadoEjemplar.BAJA if estado_fisico == EstadoFisico.DESTRUIDO else EstadoEjemplar.DISPONIBLE

    def despachar(self) -> None:
        self._exigir((EstadoEjemplar.DISPONIBLE, EstadoEjemplar.RESERVADO), "despachar")
        self.estado = EstadoEjemplar.EN_TRANSITO

    def recibir_en(self, sede_id: int, resultado: str, apartado: bool) -> None:
        """Aplica el resultado de la recepción de un remito.

        `apartado` indica si el ejemplar viaja por un préstamo (queda reservado para el socio)
        o vuelve a su sede (queda disponible).
        """
        self._exigir((EstadoEjemplar.EN_TRANSITO,), "recibir")
        if resultado == ResultadoRecepcion.FALTANTE:
            self.estado = EstadoEjemplar.EXTRAVIADO
            return
        self.sede_actual_id = sede_id
        if resultado == ResultadoRecepcion.DESTRUIDO:
            self.estado_fisico = EstadoFisico.DESTRUIDO
            self.estado = EstadoEjemplar.BAJA
            return
        if resultado == ResultadoRecepcion.DANIADO:
            self.estado_fisico = EstadoFisico.DANIADO
        self.estado = EstadoEjemplar.RESERVADO if apartado else EstadoEjemplar.DISPONIBLE

    def reparar(self, estado_fisico: str) -> None:
        """Registra una reparación: el estado físico solo puede mejorar."""
        self._exigir((EstadoEjemplar.DISPONIBLE,), "reparar")
        if estado_fisico not in EstadoFisico.mejores_que(self.estado_fisico):
            raise ErrorNegocio(f"El ejemplar está {self.estado_fisico}; "
                               "una reparación tiene que dejarlo en un estado mejor")
        self.estado_fisico = estado_fisico

    def dar_de_baja(self) -> None:
        self._exigir((EstadoEjemplar.DISPONIBLE,), "dar de baja")
        self.estado = EstadoEjemplar.BAJA
