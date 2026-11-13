"""Observadores concretos del remito (patrón Observer).

El servicio de remitos los suscribe antes de cada operación. Cada uno reacciona a los cambios de
estado del remito sin que el remito sepa qué hacen:

- ActualizadorEjemplares: estado y ubicación de cada ejemplar que viaja.
- ActualizadorPrestamos: estado de los préstamos interbibliotecarios que motivaron el envío.

Son independientes: cada uno modifica solo sus propias entidades, así que el orden de suscripción no importa.
"""
from __future__ import annotations

from ..datos.repositorios import Repositorios
from ..modelo import (Anulado, Despachado, Extraviado, ObservadorRemito, Recibido, RecibidoConIncidencia, Remito,
                      ResultadoRecepcion)
from .base import Reloj
from .operaciones import ejemplar_quedo_libre

_RECIBIDOS = (Recibido.codigo, RecibidoConIncidencia.codigo)


class ActualizadorEjemplares(ObservadorRemito):
    def __init__(self, repos: Repositorios, reloj: Reloj):
        self.repos = repos
        self.reloj = reloj
        self.mensajes: list[str] = []

    def actualizar(self, remito: Remito, estado_anterior: str, estado_nuevo: str) -> None:
        for ejemplar_id, prestamo_id in remito.ejemplares.items():
            ejemplar = self.repos.ejemplares.obtener_por_id(ejemplar_id)
            if estado_nuevo == Despachado.codigo:
                ejemplar.despachar()
            elif estado_nuevo in _RECIBIDOS or estado_nuevo == Extraviado.codigo:
                ejemplar.recibir_en(remito.sede_destino_id, remito.recepcion[ejemplar_id],
                                    apartado=prestamo_id is not None)
            elif estado_nuevo == Anulado.codigo and prestamo_id is not None:
                ejemplar.liberar()
            else:
                continue
            self.repos.ejemplares.actualizar(ejemplar)
            # Un ejemplar que volvió a su sede, o que se liberó porque no viajó, puede atender reservas
            if (estado_nuevo in _RECIBIDOS and prestamo_id is None) or estado_nuevo == Anulado.codigo:
                mensaje = ejemplar_quedo_libre(self.repos, ejemplar, self.reloj)
                if mensaje:
                    self.mensajes.append(mensaje)


class ActualizadorPrestamos(ObservadorRemito):
    def __init__(self, repos: Repositorios):
        self.repos = repos

    def actualizar(self, remito: Remito, estado_anterior: str, estado_nuevo: str) -> None:
        for ejemplar_id, prestamo_id in remito.ejemplares.items():
            if prestamo_id is None:
                continue
            prestamo = self.repos.prestamos.obtener_por_id(prestamo_id)
            if estado_nuevo == Despachado.codigo:
                prestamo.marcar_en_transito()
            elif estado_nuevo in _RECIBIDOS:
                if remito.recepcion[ejemplar_id] in (ResultadoRecepcion.OK, ResultadoRecepcion.DANIADO):
                    prestamo.marcar_listo_para_retiro()
                else:
                    prestamo.cancelar()
            elif estado_nuevo in (Extraviado.codigo, Anulado.codigo):
                prestamo.cancelar()
            else:
                continue
            self.repos.prestamos.actualizar(prestamo)
