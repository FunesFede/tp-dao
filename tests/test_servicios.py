"""Casos de uso completos sobre una base temporal."""
from datetime import date

import pytest

from biblioteca.datos.seed import cargar_datos_de_prueba
from biblioteca.modelo import ErrorNegocio
from biblioteca.reportes.exportador_csv import exportar_csv
from biblioteca.reportes.exportador_pdf import exportar_pdf


def estado_prestamo(s, prestamo_id):
    return next(p["estado"] for p in s.prestamos.listar() if p["id"] == prestamo_id)


def ejemplar(s, ejemplar_id):
    return next(e for e in s.catalogo.listar_ejemplares() if e["id"] == ejemplar_id)


def remito_en_curso(s):
    return s.remitos.listar(solo_en_curso=True)[0]["id"]


def test_prestamo_local_se_entrega_en_el_acto(s, red):
    p = s.prestamos.registrar(red["luis"].id, red["e_centro"].id, red["centro"].id, red["centro"].id)
    assert p.estado == "ACTIVO" and p.fecha_vencimiento == date(2026, 9, 15)
    assert ejemplar(s, red["e_centro"].id)["estado"] == "PRESTADO"


def test_circuito_interbibliotecario_completo(s, red, reloj):
    p = s.prestamos.registrar(red["ana"].id, red["e_centro"].id, red["centro"].id, red["norte"].id)
    assert p.estado == "SOLICITADO"
    remito = remito_en_curso(s)

    reloj.avanzar(hours=3)
    s.remitos.despachar(remito)
    assert estado_prestamo(s, p.id) == "EN_TRANSITO"          # Observer sobre préstamos
    assert ejemplar(s, red["e_centro"].id)["estado"] == "EN_TRANSITO"

    reloj.avanzar(hours=20)
    s.remitos.recibir(remito)
    assert estado_prestamo(s, p.id) == "LISTO_PARA_RETIRO"
    e = ejemplar(s, red["e_centro"].id)
    assert e["estado"] == "RESERVADO" and e["sede_actual_id"] == red["norte"].id

    reloj.avanzar(hours=2)
    s.prestamos.entregar(p.id)
    reloj.avanzar(days=24)                                    # vence a los 21 días: 3 de atraso
    resultado = s.prestamos.registrar_devolucion(p.id, red["norte"].id, "BUENO")
    # La política es la de la sede de origen (Centro, multa de $100 por día), no la de Norte
    assert resultado.sancion.descripcion().startswith("Multa de $300,00")
    assert "remito de retorno" in resultado.mensaje()

    retorno = remito_en_curso(s)
    reloj.avanzar(hours=1)
    s.remitos.despachar(retorno)
    reloj.avanzar(hours=10)
    s.remitos.recibir(retorno)
    e = ejemplar(s, red["e_centro"].id)
    assert e["estado"] == "DISPONIBLE" and e["sede_actual_id"] == red["centro"].id


def test_validaciones_al_prestar(s, red):
    centro, norte = red["centro"].id, red["norte"].id
    with pytest.raises(ErrorNegocio, match="no pertenece"):
        s.prestamos.registrar(red["ana"].id, red["e_norte"].id, centro, centro)
    s.socios.inhabilitar(red["ana"].id, "Prueba")
    with pytest.raises(ErrorNegocio, match="inhabilitado"):
        s.prestamos.registrar(red["ana"].id, red["e_centro"].id, centro, centro)
    s.socios.habilitar(red["ana"].id)
    s.prestamos.registrar(red["ana"].id, red["e_centro"].id, centro, centro)
    with pytest.raises(ErrorNegocio, match="no está disponible"):
        s.prestamos.registrar(red["luis"].id, red["e_centro"].id, centro, centro)
    s.sedes.dar_de_baja(red["sur"].id)
    with pytest.raises(ErrorNegocio, match="dada de baja"):
        s.prestamos.registrar(red["luis"].id, red["e_norte"].id, norte, red["sur"].id)


def test_suspension_por_atraso_impide_prestar(s, red, reloj):
    p = s.prestamos.registrar(red["ana"].id, red["e_norte"].id, red["norte"].id, red["norte"].id)
    reloj.avanzar(days=19)                                    # 5 días tarde, Norte suspende 2 x día
    s.prestamos.registrar_devolucion(p.id, red["norte"].id, "BUENO")
    assert s.socios.obtener(red["ana"].id).suspendido_hasta == date(2026, 9, 30)
    with pytest.raises(ErrorNegocio, match="suspendido"):
        s.prestamos.registrar(red["ana"].id, red["e_norte"].id, red["norte"].id, red["norte"].id)


def test_recepcion_con_faltante_cancela_el_prestamo(s, red, reloj):
    p = s.prestamos.registrar(red["ana"].id, red["e_centro"].id, red["centro"].id, red["norte"].id)
    remito = remito_en_curso(s)
    reloj.avanzar(hours=1)
    s.remitos.despachar(remito)
    reloj.avanzar(hours=5)
    s.remitos.recibir(remito, {red["e_centro"].id: "FALTANTE"})
    assert estado_prestamo(s, p.id) == "CANCELADO"
    assert ejemplar(s, red["e_centro"].id)["estado"] == "EXTRAVIADO"


def test_anular_remito_libera_el_ejemplar(s, red):
    p = s.prestamos.registrar(red["ana"].id, red["e_centro"].id, red["centro"].id, red["norte"].id)
    s.remitos.anular(remito_en_curso(s), "Prueba")
    assert estado_prestamo(s, p.id) == "CANCELADO"
    assert ejemplar(s, red["e_centro"].id)["estado"] == "DISPONIBLE"


def test_cancelar_prestamo_anula_el_remito_que_queda_vacio(s, red):
    p = s.prestamos.registrar(red["ana"].id, red["e_centro"].id, red["centro"].id, red["norte"].id)
    remito_id = remito_en_curso(s)
    s.prestamos.cancelar(p.id)
    detalle = s.remitos.detalle(remito_id)
    assert detalle["remito"].estado == "ANULADO" and not detalle["ejemplares"]
    assert detalle["movimientos"][-1]["estado_nuevo"] == "ANULADO"
    assert ejemplar(s, red["e_centro"].id)["estado"] == "DISPONIBLE"


def test_cancelar_un_prestamo_no_anula_un_remito_con_otros_ejemplares(s, red):
    otro = s.catalogo.agregar_ejemplar(red["libro"].id, red["centro"].id)
    p1 = s.prestamos.registrar(red["ana"].id, red["e_centro"].id, red["centro"].id, red["norte"].id)
    s.prestamos.registrar(red["luis"].id, otro.id, red["centro"].id, red["norte"].id)
    remito_id = remito_en_curso(s)
    s.prestamos.cancelar(p1.id)
    detalle = s.remitos.detalle(remito_id)
    assert detalle["remito"].estado == "EN_PREPARACION"
    assert [e["ejemplar_id"] for e in detalle["ejemplares"]] == [otro.id]


def test_reserva_se_asigna_al_devolver_y_se_retira(s, red, reloj):
    p = s.prestamos.registrar(red["luis"].id, red["e_centro"].id, red["centro"].id, red["centro"].id)
    reserva = s.reservas.crear(red["ana"].id, red["libro"].id, red["centro"].id)
    assert reserva.estado == "PENDIENTE"
    reloj.avanzar(days=2)
    s.prestamos.registrar_devolucion(p.id, red["centro"].id, "BUENO")
    asignada = next(r for r in s.reservas.listar() if r["id"] == reserva.id)
    assert asignada["estado"] == "ASIGNADA" and asignada["ejemplar_asignado_id"] == red["e_centro"].id
    s.reservas.retirar(reserva.id)
    assert ejemplar(s, red["e_centro"].id)["estado"] == "PRESTADO"


def test_reserva_asignada_expira(s, red, reloj):
    reserva = s.reservas.crear(red["ana"].id, red["libro"].id, red["centro"].id)
    assert reserva.estado == "ASIGNADA"
    reloj.avanzar(days=4)
    assert s.reservas.expirar_vencidas() == 1
    assert ejemplar(s, red["e_centro"].id)["estado"] == "DISPONIBLE"


def test_reserva_duplicada_y_sede_sin_ejemplares(s, red):
    s.reservas.crear(red["ana"].id, red["libro"].id, red["centro"].id)
    with pytest.raises(ErrorNegocio, match="reserva vigente"):
        s.reservas.crear(red["ana"].id, red["libro"].id, red["centro"].id)
    with pytest.raises(ErrorNegocio, match="no tiene ejemplares"):
        s.reservas.crear(red["ana"].id, red["libro"].id, red["sur"].id)


def test_duplicados_con_mensaje_claro(s, red):
    with pytest.raises(ErrorNegocio, match="DNI"):
        s.socios.crear("30111222", "Otra", "Persona", red["centro"].id)
    with pytest.raises(ErrorNegocio, match="ISBN"):
        s.catalogo.crear_libro("9789500000017", "Otro", "Autor")


def test_maximo_de_prestamos_abiertos(s, red):
    centro = red["centro"].id
    for _ in range(2):
        s.catalogo.agregar_ejemplar(red["libro"].id, centro)
    disponibles = s.catalogo.listar_ejemplares(red["libro"].id, centro, solo_prestables=True)
    for e in disponibles:
        s.prestamos.registrar(red["luis"].id, e["id"], centro, centro)
    otro = s.catalogo.agregar_ejemplar(red["libro"].id, centro)
    with pytest.raises(ErrorNegocio, match="3 préstamos"):
        s.prestamos.registrar(red["luis"].id, otro.id, centro, centro)


def test_no_se_da_de_baja_una_sede_con_envios_en_curso(s, red):
    s.prestamos.registrar(red["ana"].id, red["e_centro"].id, red["centro"].id, red["norte"].id)
    with pytest.raises(ErrorNegocio, match="envíos en curso"):
        s.sedes.dar_de_baja(red["norte"].id)


def test_ejemplares_de_sede_dada_de_baja_no_figuran_disponibles(s, red):
    libro_id, norte = red["libro"].id, red["norte"].id

    def disponibles_en_norte():
        return next(d["disponibles"] for d in s.catalogo.disponibilidad(libro_id) if d["sede_id"] == norte)

    assert s.catalogo.listar_libros()[0]["disponibles"] == 2 and disponibles_en_norte() == 1
    s.sedes.dar_de_baja(norte)
    assert s.catalogo.listar_libros()[0]["disponibles"] == 1
    assert disponibles_en_norte() == 0
    assert s.catalogo.listar_ejemplares(libro_id, norte, solo_prestables=True) == []
    assert ejemplar(s, red["e_norte"].id)["estado"] == "DISPONIBLE"   # el estado no se toca
    s.sedes.reactivar(norte)
    assert disponibles_en_norte() == 1


def test_listado_de_libros_cuenta_los_ejemplares_dados_de_baja(s, red):
    s.catalogo.dar_de_baja_ejemplar(red["e_norte"].id)
    fila = s.catalogo.listar_libros()[0]
    assert (fila["ejemplares"], fila["disponibles"], fila["bajas"]) == (2, 1, 1)


def test_detalle_de_una_devolucion_con_atraso(s, red, reloj):
    p = s.prestamos.registrar(red["luis"].id, red["e_centro"].id, red["centro"].id, red["centro"].id)
    reloj.avanzar(days=17)                                    # 3 días tarde; Centro cobra $100 por día
    s.prestamos.registrar_devolucion(p.id, red["norte"].id, "REGULAR", "Hoja 12 doblada")
    reloj.avanzar(days=30)                                    # el atraso no depende de la fecha de hoy
    detalle = s.prestamos.detalle_devolucion(p.id)
    d = detalle["devolucion"]
    assert (d["observaciones"], d["estado_fisico"], d["sede_recepcion"], d["dias_atraso"]) == \
        ("Hoja 12 doblada", "REGULAR", "Norte", 3)
    assert detalle["prestamo"]["titulo"] == "Rayuela" and detalle["prestamo"]["socio"] == "Gómez, Luis"
    assert detalle["sanciones"] == [{"descripcion": "Multa de $300,00 por 3 día(s) de atraso", "pagada": False}]


def test_detalle_de_una_devolucion_en_termino(s, red, reloj):
    p = s.prestamos.registrar(red["luis"].id, red["e_centro"].id, red["centro"].id, red["centro"].id)
    reloj.avanzar(days=5)
    s.prestamos.registrar_devolucion(p.id, red["centro"].id, "BUENO")
    detalle = s.prestamos.detalle_devolucion(p.id)
    assert detalle["sanciones"] == [] and detalle["devolucion"]["dias_atraso"] == 0
    assert detalle["devolucion"]["observaciones"] is None


def test_detalle_de_devolucion_de_un_prestamo_sin_devolver(s, red):
    p = s.prestamos.registrar(red["luis"].id, red["e_centro"].id, red["centro"].id, red["centro"].id)
    with pytest.raises(ErrorNegocio, match="no tiene una devolución registrada"):
        s.prestamos.detalle_devolucion(p.id)
    with pytest.raises(ErrorNegocio, match="no tiene una devolución registrada"):
        s.prestamos.detalle_devolucion(9999)


def test_vencimientos(s, red, reloj):
    s.prestamos.registrar(red["luis"].id, red["e_centro"].id, red["centro"].id, red["centro"].id)
    reloj.avanzar(days=15)
    assert s.prestamos.actualizar_vencimientos() == 1
    assert s.prestamos.listar(("VENCIDO",))[0]["dias_atraso"] == 1


def test_seed_y_reportes(base, tmp_path):
    from biblioteca.servicios import Servicios
    cargar_datos_de_prueba()
    s = Servicios()
    resumen = s.reportes.resumen()
    assert resumen["sedes"] == 4 and resumen["vencidos"] == 2 and resumen["remitos_en_curso"] == 2
    for clave in s.reportes.CATALOGO:
        reporte = s.reportes.generar(clave)
        assert reporte.filas, clave
        assert exportar_pdf(reporte, tmp_path / f"{clave}.pdf").stat().st_size > 2000
        assert exportar_csv(reporte, tmp_path / f"{clave}.csv").read_text(encoding="utf-8-sig").count("\n") >= 2
    disponibilidad = s.reportes.generar("disponibilidad")
    for fila in disponibilidad.filas:      # cada ejemplar cuenta en una sola columna
        assert fila[2] == sum(fila[3:7])
