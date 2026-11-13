"""Modo de consulta para socios: servicio y pantallas.

Usa los datos de prueba del seed (ver la tabla de DNI en biblioteca/datos/seed.py).
"""
import pytest

from biblioteca.datos.seed import cargar_datos_de_prueba
from biblioteca.modelo import ErrorNegocio
from biblioteca.presentacion.app_socio import AplicacionSocio
from biblioteca.presentacion.ingreso import PantallaIngreso
from biblioteca.servicios import Servicios
from utilidades import PaginaFalsa, elegir

LUCIA, MARTIN, VALENTINA, TOMAS, CAMILA = "33100200", "35210300", "30987654", "36543210", "40111222"


@pytest.fixture
def servicios(base):
    cargar_datos_de_prueba()
    return Servicios()


@pytest.fixture
def consulta(servicios):
    return servicios.consulta_socio


# --- servicio --------------------------------------------------------------------
def test_ingresar_con_dni_inexistente(consulta):
    with pytest.raises(ErrorNegocio, match="No hay un socio registrado con ese DNI"):
        consulta.ingresar("11222333")
    with pytest.raises(ErrorNegocio):
        consulta.ingresar("")
    assert consulta.ingresar("33.100.200").dni == LUCIA      # se normaliza igual que en Socio


def test_prestamos_y_reservas_son_solo_del_socio(servicios, consulta):
    for dni in (LUCIA, MARTIN, CAMILA):
        socio = consulta.ingresar(dni)
        prestamos = consulta.prestamos(socio.id, True) + consulta.prestamos(socio.id, False)
        reservas = consulta.reservas(socio.id)
        assert all(p["socio_id"] == socio.id for p in prestamos)
        assert all(r["socio_id"] == socio.id for r in reservas)
    # El listado general sí tiene datos de otros socios: el filtro hace algo
    assert len({p["socio_id"] for p in servicios.prestamos.listar()}) > 1
    lucia = consulta.ingresar(LUCIA)
    assert [p["estado"] for p in consulta.prestamos(lucia.id, True)] == ["ACTIVO"]


def test_no_se_cancela_la_reserva_de_otro_socio(consulta):
    camila, lucia = consulta.ingresar(CAMILA), consulta.ingresar(LUCIA)
    reserva = next(r for r in consulta.reservas(camila.id) if r["estado"] == "ASIGNADA")
    with pytest.raises(ErrorNegocio, match="La reserva no pertenece al socio"):
        consulta.cancelar_reserva(lucia.id, reserva["id"])
    assert next(r for r in consulta.reservas(camila.id) if r["id"] == reserva["id"])["estado"] == "ASIGNADA"
    assert "cancelada" in consulta.cancelar_reserva(camila.id, reserva["id"])


def test_socio_suspendido_no_puede_reservar(servicios, consulta):
    valentina = consulta.ingresar(VALENTINA)
    libro = servicios.catalogo.listar_libros()[0]
    sede = next(d for d in servicios.catalogo.disponibilidad(libro["id"]) if d["activa"] and d["total"])
    with pytest.raises(ErrorNegocio, match="suspendido"):
        consulta.reservar(valentina.id, libro["id"], sede["sede_id"])
    assert consulta.reservas(valentina.id) == []


def test_situacion_informa_deuda_y_bloqueo(consulta):
    camila = consulta.situacion(consulta.ingresar(CAMILA).id)
    assert camila["situacion"] == "habilitado" and camila["deuda"] > 0
    assert camila["deuda"] == sum(m["monto"] for m in camila["multas_impagas"])
    assert camila["max_prestamos"] == 3
    assert consulta.situacion(consulta.ingresar(VALENTINA).id)["situacion"].startswith("suspendido")
    tomas = consulta.situacion(consulta.ingresar(TOMAS).id)
    assert tomas["situacion"].startswith("inhabilitado") and "Documentación" in tomas["situacion"]
    assert consulta.situacion(consulta.ingresar(LUCIA).id)["prestamos_abiertos"] == 1


# --- interfaz --------------------------------------------------------------------
def ingresar(servicios, dni):
    pagina = PaginaFalsa()
    ingreso = PantallaIngreso(pagina, servicios)
    pagina.add(ingreso.build())
    ingreso.dni.value = dni
    ingreso.dni.on_submit(None)                               # Enter en el campo DNI
    return ingreso, pagina


def test_socio_reserva_desde_el_catalogo_y_la_cancela(servicios):
    ingreso, pagina = ingresar(servicios, LUCIA)
    app = ingreso.aplicacion
    assert isinstance(app, AplicacionSocio) and len(pagina.controls) == 1
    for indice in range(len(app.pantallas)):                 # todas las pantallas cargan sin errores
        app.mostrar(indice)
    assert not pagina.mensajes

    app.mostrar(0)
    catalogo = app.pantallas[0]
    libro_id = next(i for i, f in catalogo.libros.items() if f["disponibles"])
    catalogo.tabla_libros._seleccionar(libro_id)
    assert not catalogo.btn_reservar.disabled and catalogo.sedes_con_copias
    catalogo.reservar(None)
    (sede,) = pagina.campos()
    elegir(sede, next(d["sede"] for d in catalogo.sedes_con_copias if d["disponibles"]))
    pagina.aceptar()
    assert not pagina.dialogos and "Reserva registrada" in pagina.ultimo_mensaje()

    app.mostrar(2)
    reservas = app.pantallas[2]
    reserva_id = next(i for i, f in reservas.filas.items() if f["libro_id"] == libro_id)
    reservas.tabla._seleccionar(reserva_id)
    assert not reservas.btn_cancelar.disabled
    reservas.cancelar(None)
    pagina.aceptar()
    assert reservas.filas[reserva_id]["estado"] == "CANCELADA"
    reservas.al_seleccionar(reserva_id)
    assert reservas.btn_cancelar.disabled                   # ya no está vigente


def test_dni_inexistente_muestra_el_error_sin_cambiar_de_pantalla(servicios):
    ingreso, pagina = ingresar(servicios, "11222333")
    pantalla_de_ingreso = pagina.controls[0]
    assert ingreso.error.visible and "No hay un socio" in ingreso.error.value
    assert ingreso.aplicacion is None and pagina.controls == [pantalla_de_ingreso]


def test_situacion_en_pantalla_y_salir(servicios):
    ingreso, pagina = ingresar(servicios, CAMILA)
    app = ingreso.aplicacion
    app.mostrar(3)
    situacion = app.pantallas[3]
    assert situacion.estado.value == "Habilitado" and situacion.total.value.startswith("Total adeudado")
    assert situacion.tabla.tabla.rows and not situacion.aviso.visible

    pantalla_de_la_app = pagina.controls[0]
    app.al_salir()
    assert len(pagina.controls) == 1 and pagina.controls[0] is not pantalla_de_la_app


def test_socio_suspendido_ve_el_aviso(servicios):
    ingreso, pagina = ingresar(servicios, VALENTINA)
    ingreso.aplicacion.mostrar(3)
    situacion = ingreso.aplicacion.pantallas[3]
    assert situacion.estado.value == "Suspendido" and situacion.aviso.visible
    assert situacion.motivo.value.startswith("Está suspendido hasta el ")


def test_socio_inhabilitado_ve_el_motivo(servicios):
    ingreso, pagina = ingresar(servicios, TOMAS)
    ingreso.aplicacion.mostrar(3)
    situacion = ingreso.aplicacion.pantallas[3]
    assert situacion.estado.value == "Inhabilitado" and situacion.aviso.visible
    assert situacion.motivo.value == "Motivo: Documentación de domicilio pendiente."
