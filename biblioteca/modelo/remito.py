"""Remito de envío entre sedes.

Patrón State (ciclo de vida):

    EN_PREPARACION ──despachar──▶ DESPACHADO ──registrar_transito──▶ EN_TRANSITO ◀─┐
          │                           │                                  │  │       │
        anular                     recibir / declarar_extravio           │  └───────┘ (checkpoint)
          ▼                           ▼                                  ▼
       ANULADO          RECIBIDO | RECIBIDO_CON_INCIDENCIA | EXTRAVIADO

- Contexto: Remito. Guarda una referencia al objeto estado y delega cada operación.
- Estado abstracto: EstadoRemito. Por defecto rechaza todo con TransicionInvalida.
- Estados concretos: cada uno habilita sus operaciones y decide la transición.

Patrón Observer (consecuencias de cada transición):

- Sujeto: Remito, con suscribir() / desuscribir() / _notificar()
  (equivalen a attach() / detach() / notify() de la cátedra).
- Observador: ObservadorRemito.actualizar() (equivale a update()).
- Observadores concretos: en servicios/observadores.py (actualizan ejemplares y préstamos).

El remito no conoce la base de datos ni a sus observadores concretos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from .catalogo import ResultadoRecepcion
from .excepciones import ErrorNegocio, TransicionInvalida


@dataclass(frozen=True)
class Movimiento:
    estado_anterior: str | None
    estado_nuevo: str
    fecha_hora: datetime
    sede_id: int | None
    observacion: str = ""


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------
class ObservadorRemito(ABC):
    @abstractmethod
    def actualizar(self, remito: Remito, estado_anterior: str, estado_nuevo: str) -> None:
        """Se invoca después de cada cambio de estado del remito."""


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class EstadoRemito(ABC):
    codigo: str = ""

    def agregar_ejemplar(self, remito: Remito, ejemplar_id: int, prestamo_id: int | None) -> None:
        self._rechazar("agregar ejemplares a")

    def quitar_ejemplar(self, remito: Remito, ejemplar_id: int) -> None:
        self._rechazar("quitar ejemplares de")

    def despachar(self, remito: Remito, sede_id: int) -> None:
        self._rechazar("despachar")

    def registrar_transito(self, remito: Remito, sede_id: int | None, observacion: str) -> None:
        self._rechazar("registrar el tránsito de")

    def recibir(self, remito: Remito, sede_id: int, incidencias: dict[int, str]) -> None:
        self._rechazar("recibir")

    def declarar_extravio(self, remito: Remito, sede_id: int | None, observacion: str) -> None:
        self._rechazar("declarar extraviado")

    def anular(self, remito: Remito, sede_id: int, motivo: str) -> None:
        self._rechazar("anular")

    def _rechazar(self, accion: str) -> None:
        raise TransicionInvalida(f"No se puede {accion} un remito en estado {self.codigo}")


class EnPreparacion(EstadoRemito):
    codigo = "EN_PREPARACION"

    def agregar_ejemplar(self, remito, ejemplar_id, prestamo_id):
        if ejemplar_id in remito.ejemplares:
            raise ErrorNegocio(f"El ejemplar ya está en el remito {remito.numero}")
        remito.ejemplares[ejemplar_id] = prestamo_id

    def quitar_ejemplar(self, remito, ejemplar_id):
        if ejemplar_id not in remito.ejemplares:
            raise ErrorNegocio(f"El ejemplar no está en el remito {remito.numero}")
        del remito.ejemplares[ejemplar_id]

    def despachar(self, remito, sede_id):
        if sede_id != remito.sede_origen_id:
            raise TransicionInvalida("Solo la sede de origen puede despachar el remito")
        if not remito.ejemplares:
            raise TransicionInvalida("No se puede despachar un remito vacío")
        remito._cambiar_estado(Despachado(), sede_id, "Despachado desde la sede de origen")

    def anular(self, remito, sede_id, motivo):
        remito._cambiar_estado(Anulado(), sede_id, motivo or "Anulado")


class EnCamino(EstadoRemito):
    """Comportamiento común a DESPACHADO y EN_TRANSITO."""

    def registrar_transito(self, remito, sede_id, observacion):
        remito._cambiar_estado(EnTransito(), sede_id, observacion or "Checkpoint de tránsito")

    def recibir(self, remito, sede_id, incidencias):
        if sede_id != remito.sede_destino_id:
            raise TransicionInvalida("Solo la sede de destino puede recibir el remito")
        desconocidos = set(incidencias) - set(remito.ejemplares)
        if desconocidos:
            raise ErrorNegocio("Hay incidencias sobre ejemplares que no viajan en el remito")
        invalidas = set(incidencias.values()) - set(ResultadoRecepcion.INCIDENCIAS)
        if invalidas:
            raise ErrorNegocio(f"Incidencias no válidas: {', '.join(sorted(invalidas))}")

        remito.recepcion = {e: incidencias.get(e, ResultadoRecepcion.OK) for e in remito.ejemplares}
        if incidencias:
            detalle = ", ".join(sorted(set(incidencias.values())))
            remito._cambiar_estado(RecibidoConIncidencia(), sede_id, f"Recibido con incidencias: {detalle}")
        else:
            remito._cambiar_estado(Recibido(), sede_id, "Recepción conforme")

    def declarar_extravio(self, remito, sede_id, observacion):
        remito.recepcion = {e: ResultadoRecepcion.FALTANTE for e in remito.ejemplares}
        remito._cambiar_estado(Extraviado(), sede_id, observacion or "Envío declarado extraviado")


class Despachado(EnCamino):
    codigo = "DESPACHADO"


class EnTransito(EnCamino):
    codigo = "EN_TRANSITO"


class EstadoFinal(EstadoRemito):
    """Estados sin transiciones: toda operación se rechaza."""


class Recibido(EstadoFinal):
    codigo = "RECIBIDO"


class RecibidoConIncidencia(EstadoFinal):
    codigo = "RECIBIDO_CON_INCIDENCIA"


class Extraviado(EstadoFinal):
    codigo = "EXTRAVIADO"


class Anulado(EstadoFinal):
    codigo = "ANULADO"


ESTADOS: dict[str, type[EstadoRemito]] = {
    cls.codigo: cls
    for cls in (EnPreparacion, Despachado, EnTransito, Recibido,
                RecibidoConIncidencia, Extraviado, Anulado)
}


# ---------------------------------------------------------------------------
# Contexto y sujeto
# ---------------------------------------------------------------------------
class Remito:
    def __init__(
        self,
        numero: str,
        sede_origen_id: int,
        sede_destino_id: int,
        estado: EstadoRemito | None = None,
        ejemplares: dict[int, int | None] | None = None,
        recepcion: dict[int, str] | None = None,
        historial: list[Movimiento] | None = None,
        fecha_creacion: datetime | None = None,
        id: int | None = None,
        reloj: Callable[[], datetime] | None = None,
    ):
        if sede_origen_id == sede_destino_id:
            raise ErrorNegocio("La sede de origen y la de destino deben ser distintas")
        self.id = id
        self.numero = numero
        self.sede_origen_id = sede_origen_id
        self.sede_destino_id = sede_destino_id
        self.reloj = reloj or (lambda: datetime.now().replace(microsecond=0))
        self._estado = estado or EnPreparacion()
        self.ejemplares: dict[int, int | None] = dict(ejemplares or {})   # ejemplar_id -> prestamo_id
        self.recepcion: dict[int, str] = dict(recepcion or {})            # ejemplar_id -> resultado
        self.fecha_creacion = fecha_creacion or self.reloj()
        self.historial: list[Movimiento] = list(historial or [])
        self._observadores: list[ObservadorRemito] = []
        if not self.historial:
            self.historial.append(
                Movimiento(None, self._estado.codigo, self.fecha_creacion, sede_origen_id, "Remito creado"))

    @staticmethod
    def estado_desde_codigo(codigo: str) -> EstadoRemito:
        try:
            return ESTADOS[codigo]()
        except KeyError:
            raise ValueError(f"Estado de remito desconocido: {codigo}") from None

    # --- Observer ------------------------------------------------------------
    def suscribir(self, observador: ObservadorRemito) -> None:
        self._observadores.append(observador)

    def desuscribir(self, observador: ObservadorRemito) -> None:
        self._observadores.remove(observador)

    def _notificar(self, anterior: str, nuevo: str) -> None:
        for observador in self._observadores:
            observador.actualizar(self, anterior, nuevo)

    # --- consultas -----------------------------------------------------------
    @property
    def estado(self) -> str:
        return self._estado.codigo

    def tiempo_en_transito(self) -> timedelta | None:
        despacho = next((m for m in self.historial if m.estado_nuevo == Despachado.codigo), None)
        llegada = next((m for m in self.historial
                        if m.estado_nuevo in (Recibido.codigo, RecibidoConIncidencia.codigo)), None)
        if despacho and llegada:
            return llegada.fecha_hora - despacho.fecha_hora
        return None

    # --- operaciones (delegan en el estado) ----------------------------------
    def agregar_ejemplar(self, ejemplar_id: int, prestamo_id: int | None = None) -> None:
        self._estado.agregar_ejemplar(self, ejemplar_id, prestamo_id)

    def quitar_ejemplar(self, ejemplar_id: int) -> None:
        self._estado.quitar_ejemplar(self, ejemplar_id)

    def despachar(self, sede_id: int) -> None:
        self._estado.despachar(self, sede_id)

    def registrar_transito(self, sede_id: int | None = None, observacion: str = "") -> None:
        self._estado.registrar_transito(self, sede_id, observacion)

    def recibir(self, sede_id: int, incidencias: dict[int, str] | None = None) -> None:
        self._estado.recibir(self, sede_id, incidencias or {})

    def declarar_extravio(self, sede_id: int | None = None, observacion: str = "") -> None:
        self._estado.declarar_extravio(self, sede_id, observacion)

    def anular(self, sede_id: int, motivo: str = "") -> None:
        self._estado.anular(self, sede_id, motivo)

    # --- uso interno de los estados ------------------------------------------
    def _cambiar_estado(self, nuevo: EstadoRemito, sede_id: int | None, observacion: str) -> None:
        anterior = self._estado.codigo
        ahora = self.reloj()
        if self.historial and ahora < self.historial[-1].fecha_hora:
            raise ErrorNegocio("La fecha del movimiento no puede ser anterior al último registrado")
        self.historial.append(Movimiento(anterior, nuevo.codigo, ahora, sede_id, observacion))
        self._estado = nuevo
        self._notificar(anterior, nuevo.codigo)

    def __repr__(self) -> str:
        return (f"Remito({self.numero}, {self.sede_origen_id}->{self.sede_destino_id}, "
                f"{self.estado}, ejemplares={list(self.ejemplares)})")
