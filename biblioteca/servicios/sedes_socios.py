from __future__ import annotations

from ..modelo import ErrorNegocio, Multa, PoliticaSancion, Sede, Socio
from .base import ServicioBase


class ServicioSedes(ServicioBase):
    def listar(self, solo_activas: bool = False) -> list[Sede]:
        with self._transaccion() as r:
            return r.sedes.listar(solo_activas)

    def obtener(self, sede_id: int) -> Sede:
        with self._transaccion() as r:
            return self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")

    def crear(self, nombre: str, direccion: str, telefono: str | None, email: str | None,
              horario: str | None, politica_sancion: str, parametro_sancion: float | None) -> Sede:
        sede = Sede(nombre=nombre, direccion=direccion, telefono=telefono or None, email=email or None,
                    horario=horario or None, politica_sancion=politica_sancion,
                    **self._parametros_sancion(politica_sancion, parametro_sancion))
        with self._transaccion() as r:
            r.sedes.crear(sede)
        return sede

    def actualizar(self, sede_id: int, nombre: str, direccion: str, telefono: str | None,
                   email: str | None, horario: str | None, politica_sancion: str,
                   parametro_sancion: float | None) -> Sede:
        with self._transaccion() as r:
            actual = self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")
            sede = Sede(nombre=nombre, direccion=direccion, telefono=telefono or None,
                        email=email or None, horario=horario or None, politica_sancion=politica_sancion,
                        activa=actual.activa, fecha_baja=actual.fecha_baja, id=sede_id,
                        **self._parametros_sancion(politica_sancion, parametro_sancion))
            r.sedes.actualizar(sede)
        return sede

    def dar_de_baja(self, sede_id: int) -> None:
        with self._transaccion() as r:
            sede = self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")
            if r.sedes.contar_remitos_en_curso(sede_id):
                raise ErrorNegocio(f"La sede {sede.nombre} tiene envíos en curso; "
                                   "hay que recibirlos o anularlos antes de darla de baja")
            sede.dar_de_baja(self.ahora().date())
            r.sedes.actualizar(sede)

    def reactivar(self, sede_id: int) -> None:
        with self._transaccion() as r:
            sede = self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")
            sede.reactivar()
            r.sedes.actualizar(sede)

    @staticmethod
    def _parametros_sancion(politica: str, valor: float | None) -> dict:
        if valor is None:
            raise ErrorNegocio("Indique el valor de la política de sanción")
        if politica == PoliticaSancion.SUSPENSION:
            if float(valor) != int(valor):
                raise ErrorNegocio("El factor de suspensión debe ser un número entero")
            return {"factor_suspension": int(valor)}
        return {"monto_por_dia": float(valor)}


class ServicioSocios(ServicioBase):
    def listar(self, texto: str = "") -> list[dict]:
        hoy = self.ahora().date()
        with self._transaccion() as r:
            filas = r.socios.listar_resumen(texto)
        for fila in filas:
            fila["situacion"] = fila["socio"].motivo_bloqueo(hoy) or "habilitado"
        return filas

    def obtener(self, socio_id: int) -> Socio:
        with self._transaccion() as r:
            return self._obtener(r.socios.obtener_por_id(socio_id), "el socio")

    def crear(self, dni: str, nombre: str, apellido: str, sede_id: int,
              email: str | None = None, telefono: str | None = None) -> Socio:
        socio = Socio(dni=dni, nombre=nombre, apellido=apellido, sede_id=sede_id, email=email,
                      telefono=telefono or None, fecha_alta=self.ahora().date())
        with self._transaccion() as r:
            sede = self._obtener(r.sedes.obtener_por_id(sede_id), "la sede")
            sede.exigir_activa()
            r.socios.crear(socio)
        return socio

    def actualizar(self, socio_id: int, dni: str, nombre: str, apellido: str, sede_id: int,
                   email: str | None, telefono: str | None) -> Socio:
        with self._transaccion() as r:
            actual = self._obtener(r.socios.obtener_por_id(socio_id), "el socio")
            socio = Socio(dni=dni, nombre=nombre, apellido=apellido, sede_id=sede_id, email=email,
                          telefono=telefono or None, suspendido_hasta=actual.suspendido_hasta,
                          inhabilitado_manual=actual.inhabilitado_manual,
                          motivo_inhabilitacion=actual.motivo_inhabilitacion,
                          fecha_alta=actual.fecha_alta, id=socio_id)
            if sede_id != actual.sede_id:
                self._obtener(r.sedes.obtener_por_id(sede_id), "la sede").exigir_activa()
            r.socios.actualizar(socio)
        return socio

    def inhabilitar(self, socio_id: int, motivo: str) -> None:
        with self._transaccion() as r:
            socio = self._obtener(r.socios.obtener_por_id(socio_id), "el socio")
            socio.inhabilitar(motivo)
            r.socios.actualizar(socio)

    def habilitar(self, socio_id: int) -> None:
        with self._transaccion() as r:
            socio = self._obtener(r.socios.obtener_por_id(socio_id), "el socio")
            socio.habilitar()
            r.socios.actualizar(socio)

    def listar_sanciones(self, socio_id: int | None = None) -> list[dict]:
        with self._transaccion() as r:
            return r.sanciones.listar_resumen(socio_id)

    def pagar_multa(self, sancion_id: int) -> None:
        with self._transaccion() as r:
            sancion = self._obtener(r.sanciones.obtener_por_id(sancion_id), "la sanción")
            if not isinstance(sancion, Multa):
                raise ErrorNegocio("Solo se pueden pagar las sanciones monetarias")
            sancion.pagar()
            r.sanciones.marcar_pagada(sancion)
