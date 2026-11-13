"""Pruebas del modelo, sin base de datos."""
from datetime import date, datetime

import pytest

from biblioteca.modelo import (CalculadoraSancion, Ejemplar, ErrorNegocio, Libro, Multa, ObservadorRemito,
                               Prestamo, Remito, SancionMonetaria, SancionSuspension, Sede, Socio,
                               Suspension, TransicionInvalida)

AHORA = datetime(2026, 9, 1, 10, 0)


def remito_con_ejemplar():
    r = Remito("R-1", 1, 2, reloj=lambda: AHORA)
    r.agregar_ejemplar(10, prestamo_id=100)
    return r


# --- State ------------------------------------------------------------------
def test_ciclo_completo_del_remito_registra_cada_movimiento():
    r = remito_con_ejemplar()
    r.despachar(1)
    r.registrar_transito(observacion="Centro de distribución")
    r.registrar_transito(observacion="Segundo checkpoint")
    r.recibir(2)
    assert r.estado == "RECIBIDO"
    assert [m.estado_nuevo for m in r.historial] == [
        "EN_PREPARACION", "DESPACHADO", "EN_TRANSITO", "EN_TRANSITO", "RECIBIDO"]


def test_operaciones_no_permitidas_por_el_estado():
    r = remito_con_ejemplar()
    with pytest.raises(TransicionInvalida):
        r.recibir(2)                 # todavía no salió
    r.despachar(1)
    with pytest.raises(TransicionInvalida):
        r.agregar_ejemplar(11)       # ya está cerrado
    with pytest.raises(TransicionInvalida):
        r.anular(1)                  # solo se anula en preparación
    r.recibir(2)
    with pytest.raises(TransicionInvalida):
        r.despachar(1)               # estado final


def test_solo_el_origen_despacha_y_solo_el_destino_recibe():
    r = remito_con_ejemplar()
    with pytest.raises(TransicionInvalida):
        r.despachar(2)
    r.despachar(1)
    with pytest.raises(TransicionInvalida):
        r.recibir(1)


def test_no_se_despacha_un_remito_vacio():
    with pytest.raises(TransicionInvalida):
        Remito("R-1", 1, 2).despachar(1)


def test_recepcion_con_incidencia():
    r = remito_con_ejemplar()
    r.agregar_ejemplar(11)
    r.despachar(1)
    r.recibir(2, {11: "DANIADO"})
    assert r.estado == "RECIBIDO_CON_INCIDENCIA"
    assert r.recepcion == {10: "OK", 11: "DANIADO"}


def test_extravio_marca_todo_faltante():
    r = remito_con_ejemplar()
    r.despachar(1)
    r.declarar_extravio()
    assert r.estado == "EXTRAVIADO" and r.recepcion == {10: "FALTANTE"}


def test_el_estado_se_reconstruye_desde_el_codigo():
    r = Remito("R-1", 1, 2, estado=Remito.estado_desde_codigo("EN_TRANSITO"), ejemplares={10: None})
    r.recibir(2)
    assert r.estado == "RECIBIDO"


# --- Observer ---------------------------------------------------------------
def test_los_observadores_reciben_cada_cambio_de_estado():
    class Registro(ObservadorRemito):
        def __init__(self):
            self.cambios = []

        def actualizar(self, remito, anterior, nuevo):
            self.cambios.append((anterior, nuevo))

    r = remito_con_ejemplar()
    registro = Registro()
    r.suscribir(registro)
    r.despachar(1)
    r.recibir(2)
    assert registro.cambios == [("EN_PREPARACION", "DESPACHADO"), ("DESPACHADO", "RECIBIDO")]


# --- Strategy ---------------------------------------------------------------
def prestamo_vencido_hace(dias: int) -> Prestamo:
    p = Prestamo.nuevo(1, 1, 1, 1, AHORA)
    p.id = 7
    p.entregar(AHORA)
    p.fecha_vencimiento = date(2026, 9, 1)
    return p, datetime(2026, 9, 1 + dias, 12, 0)


def test_estrategia_monetaria():
    socio = Socio("30111222", "Ana", "Pérez", 1, id=1)
    p, devolucion = prestamo_vencido_hace(5)
    sancion = CalculadoraSancion(SancionMonetaria(150)).calcular(p, socio, devolucion)
    assert isinstance(sancion, Multa) and sancion.monto == 750 and not sancion.pagada


def test_estrategia_suspension_suspende_al_socio():
    socio = Socio("30111222", "Ana", "Pérez", 1, id=1)
    p, devolucion = prestamo_vencido_hace(5)
    sancion = CalculadoraSancion(SancionSuspension(2)).calcular(p, socio, devolucion)
    assert isinstance(sancion, Suspension)
    assert socio.suspendido_hasta == date(2026, 9, 16)
    assert socio.esta_inhabilitado(date(2026, 9, 10))


def test_sin_atraso_no_hay_sancion():
    socio = Socio("30111222", "Ana", "Pérez", 1, id=1)
    p, _ = prestamo_vencido_hace(0)
    assert CalculadoraSancion(SancionMonetaria(100)).calcular(p, socio, datetime(2026, 9, 1, 18)) is None


def test_la_sede_arma_su_estrategia():
    assert isinstance(Sede("A", "x", monto_por_dia=10).estrategia_sancion(), SancionMonetaria)
    assert isinstance(Sede("B", "y", politica_sancion="SUSPENSION", factor_suspension=2).estrategia_sancion(),
                      SancionSuspension)


# --- validaciones de entidades ---------------------------------------------
@pytest.mark.parametrize("datos", [
    dict(dni="123", nombre="A", apellido="B", sede_id=1),
    dict(dni="30111222", nombre="", apellido="B", sede_id=1),
    dict(dni="30111222", nombre="A", apellido="B", sede_id=1, email="sin-arroba"),
])
def test_socio_invalido(datos):
    with pytest.raises(ErrorNegocio):
        Socio(**datos)


def test_isbn_invalido():
    with pytest.raises(ErrorNegocio):
        Libro("12345", "T", "A")


def test_sede_requiere_parametro_de_su_politica():
    with pytest.raises(ErrorNegocio):
        Sede("A", "x", politica_sancion="SUSPENSION")


def test_suspension_no_se_acorta():
    socio = Socio("30111222", "Ana", "Pérez", 1, suspendido_hasta=date(2026, 10, 1))
    socio.suspender_hasta(date(2026, 9, 20))
    assert socio.suspendido_hasta == date(2026, 10, 1)


def test_ejemplar_solo_se_presta_si_esta_disponible_o_apartado():
    e = Ejemplar(1, 1, 1, "X")
    e.prestar()
    with pytest.raises(ErrorNegocio):
        e.prestar()


def test_al_devolver_el_estado_fisico_no_puede_mejorar():
    e = Ejemplar(1, 1, 1, "X", estado_fisico="REGULAR")
    e.prestar()
    with pytest.raises(ErrorNegocio, match="no puede mejorar"):
        e.devolver(1, "BUENO")
    e.devolver(1, "DANIADO")
    assert e.estado_fisico == "DANIADO" and e.estado == "DISPONIBLE"


def test_reparar_solo_mejora_el_estado_fisico():
    e = Ejemplar(1, 1, 1, "X", estado_fisico="DANIADO")
    with pytest.raises(ErrorNegocio, match="estado mejor"):
        e.reparar("DESTRUIDO")
    with pytest.raises(ErrorNegocio, match="estado mejor"):
        e.reparar("DANIADO")
    e.reparar("REGULAR")
    assert e.estado_fisico == "REGULAR"
    e.prestar()
    with pytest.raises(ErrorNegocio):                  # prestado: no está en la biblioteca para repararlo
        e.reparar("BUENO")
