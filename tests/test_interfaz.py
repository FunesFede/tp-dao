"""Pruebas de la interfaz del personal, sin abrir ventanas (ver utilidades.PaginaFalsa)."""
import pytest

from biblioteca.datos.seed import cargar_datos_de_prueba
from biblioteca.presentacion.app import AplicacionBiblioteca
from biblioteca.servicios import Servicios
from utilidades import PaginaFalsa, elegir


@pytest.fixture
def app(base):
    cargar_datos_de_prueba()
    pagina = PaginaFalsa()
    aplicacion = AplicacionBiblioteca(pagina, Servicios())
    aplicacion.build()
    return aplicacion, pagina


def pantalla(aplicacion, nombre):
    clase = {"sedes": 1, "socios": 2, "catalogo": 3, "prestamos": 4, "remitos": 5, "reservas": 6, "reportes": 7}
    aplicacion.mostrar(clase[nombre])
    return aplicacion.pantallas[clase[nombre]]


def test_todas_las_pantallas_cargan(app):
    aplicacion, pagina = app
    for indice in range(len(aplicacion.pantallas)):
        aplicacion.mostrar(indice)
    assert not pagina.mensajes


def test_nueva_sede_con_politica_de_suspension(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "sedes")
    p.nueva(None)
    nombre, direccion, telefono, email, horario, politica, valor = pagina.campos()
    nombre.value, direccion.value = "Sede Oeste", "Av. Duarte Quirós 3000"
    elegir(politica, "Suspensión")
    assert "suspensión" in valor.label
    valor.value = "3"
    pagina.aceptar()
    assert pagina.ultimo_mensaje() == "Sede creada" and not pagina.dialogos
    assert any(s.nombre == "Sede Oeste" and s.factor_suspension == 3 for s in p.sedes.values())


def test_nuevo_prestamo_interbibliotecario_desde_el_formulario(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "prestamos")
    p.nuevo(None)
    socio, libro, origen, destino, ejemplar = pagina.campos()
    elegir(socio, "Medina")
    elegir(libro, "El Aleph")
    elegir(origen, "Sede Norte")
    assert ejemplar.value is not None                 # se cargan los ejemplares prestables
    elegir(destino, "Biblioteca Central")
    pagina.aceptar()
    assert "interbibliotecario" in pagina.ultimo_mensaje() and not pagina.dialogos


def test_prestamo_a_socio_suspendido_muestra_el_error(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "prestamos")
    p.nuevo(None)
    socio, libro, origen, destino, ejemplar = pagina.campos()
    elegir(socio, "Ruiz")
    elegir(libro, "El Aleph")
    elegir(origen, "Sede Norte")
    pagina.aceptar()
    assert "suspendido" in pagina.error_en_dialogo()  # el error se ve dentro del formulario
    assert pagina.dialogos                            # el formulario queda abierto para corregir


def test_devolucion_con_atraso_desde_la_pantalla(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "prestamos")
    vencido = next(i for i, f in p.filas.items() if f["estado"] == "VENCIDO")
    p.tabla._seleccionar(vencido)
    assert not p.btn_devolver.disabled
    p.devolver(None)
    pagina.aceptar()
    assert "Multa" in pagina.ultimo_mensaje()


def test_recibir_remito_con_incidencia(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "remitos")
    en_transito = next(i for i, f in p.filas.items() if f["estado"] == "EN_TRANSITO")
    p.tabla._seleccionar(en_transito)
    assert p.botones["recibir"].visible and not p.botones["despachar"].visible
    p.recibir(None)
    (resultado,) = pagina.campos()
    elegir(resultado, "Dañado")
    pagina.aceptar()
    assert "recibido" in pagina.ultimo_mensaje().lower()
    assert p.filas[en_transito]["estado"] == "RECIBIDO_CON_INCIDENCIA"


def test_reserva_y_retiro(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "reservas")
    asignada = next(i for i, f in p.filas.items() if f["estado"] == "ASIGNADA")
    p.tabla._seleccionar(asignada)
    p.retirar(None)
    pagina.aceptar()
    assert "Préstamo" in pagina.ultimo_mensaje()


def test_alta_de_libro_y_ejemplar(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "catalogo")
    p.nuevo_libro(None)
    isbn, tipo, titulo, autor, editorial, anio = pagina.campos()
    isbn.value, titulo.value = "978-950-00-0099-1", "Adán Buenosayres"
    autor.value, anio.value = "Leopoldo Marechal", "1948"
    pagina.aceptar()
    libro_id = next(i for i, f in p.libros.items() if f["titulo"] == "Adán Buenosayres")
    p.tabla_libros._seleccionar(libro_id)
    p.agregar_ejemplar(None)
    sede, codigo = pagina.campos()
    elegir(sede, "Sede Sur")
    pagina.aceptar()
    assert "agregado" in pagina.ultimo_mensaje()
    assert len(p.ejemplares) == 1


def test_reportes_se_exportan(app, tmp_path, monkeypatch):
    from biblioteca.presentacion.pantallas import reportes
    monkeypatch.setattr(reportes, "CARPETA_EXPORTES", tmp_path)
    aplicacion, pagina = app
    p = pantalla(aplicacion, "reportes")
    for clave in aplicacion.servicios.reportes.CATALOGO:
        p.seleccionar(clave)
        p.exportar_pdf(None)
        p.exportar_csv(None)
    assert len(list(tmp_path.glob("*.pdf"))) == 6 and len(list(tmp_path.glob("*.csv"))) == 6


def test_libro_con_isbn_duplicado_muestra_el_error_en_el_formulario(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "catalogo")
    isbn_existente = next(iter(p.libros.values()))["isbn"]
    p.nuevo_libro(None)
    isbn, tipo, titulo, autor, editorial, anio = pagina.campos()
    isbn.value, titulo.value, autor.value = isbn_existente, "Repetido", "Alguien"
    pagina.aceptar()
    assert pagina.error_en_dialogo() and pagina.dialogos     # el error se ve y el formulario sigue abierto
    isbn.value = "9789999999999"
    pagina.aceptar()
    assert not pagina.dialogos and "Libro creado" in pagina.ultimo_mensaje()


def test_nuevo_prestamo_solo_ofrece_sedes_con_ejemplares(app):
    aplicacion, pagina = app
    aplicacion.servicios.catalogo.crear_libro("9789999999990", "Sin ejemplares", "Nadie")
    p = pantalla(aplicacion, "prestamos")
    p.nuevo(None)
    socio, libro, origen, destino, ejemplar = pagina.campos()
    assert origen.disabled and ejemplar.disabled and destino.disabled   # sin libro no hay nada que elegir

    elegir(libro, "El Aleph")
    assert origen.options and all("disponible" in o.text for o in origen.options)
    elegir(origen, "Sede Norte")
    assert not ejemplar.disabled and ejemplar.value and not destino.disabled

    elegir(libro, "Sin ejemplares")
    assert origen.disabled and not origen.options and ejemplar.disabled and destino.disabled


def test_nueva_reserva_ofrece_solo_libros_de_la_sede(app):
    aplicacion, pagina = app
    servicios = aplicacion.servicios
    servicios.sedes.crear("Sede Vacía", "Calle 1", None, None, None, "MONETARIA", 10)
    p = pantalla(aplicacion, "reservas")
    p.nueva(None)
    socio, sede, libro = pagina.campos()
    assert libro.disabled and not libro.options                    # sin sede no hay libros

    elegir(sede, "Biblioteca Central")
    propios = {str(f["id"]) for f in servicios.catalogo.libros_de_sede(int(sede.value))}
    assert not libro.disabled and {o.key for o in libro.options} == propios

    elegir(sede, "Sede Vacía")
    assert libro.disabled and not libro.options

    elegir(sede, "Biblioteca Central")
    elegir(socio, "Medina")
    elegir(libro, next(o.text for o in libro.options if "sin disponibles" not in o.text))
    pagina.aceptar()
    assert not pagina.dialogos and "Reserva registrada" in pagina.ultimo_mensaje()


def test_devolucion_parte_del_estado_fisico_del_ejemplar(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "prestamos")
    activo = next(i for i, f in p.filas.items() if f["estado"] == "ACTIVO")
    p.filas[activo]["estado_fisico_ejemplar"] = "REGULAR"   # como si el ejemplar ya hubiera vuelto gastado
    p.tabla._seleccionar(activo)
    p.devolver(None)
    recepcion, estado, observaciones = pagina.campos()
    assert estado.value == "REGULAR"
    assert [o.key for o in estado.options] == ["REGULAR", "DANIADO", "DESTRUIDO"]


def test_reparar_ejemplar_desde_el_catalogo(app):
    aplicacion, pagina = app
    servicios = aplicacion.servicios
    libro = servicios.catalogo.crear_libro("9789999999983", "Para reparar", "Alguien")
    sede = servicios.sedes.listar(solo_activas=True)[0]
    ejemplar = servicios.catalogo.agregar_ejemplar(libro.id, sede.id)
    p = pantalla(aplicacion, "catalogo")
    p.tabla_libros._seleccionar(libro.id)
    p.tabla_ejemplares._seleccionar(ejemplar.id)
    assert p.btn_reparar.disabled                      # en estado Bueno no hay nada que reparar

    p.ejemplares[ejemplar.id]["estado_fisico"] = "DANIADO"   # como si hubiera vuelto dañado
    with servicios.catalogo._transaccion() as r:
        e = r.ejemplares.obtener_por_id(ejemplar.id)
        e.estado_fisico = "DANIADO"
        r.ejemplares.actualizar(e)
    p.al_seleccionar_ejemplar(ejemplar.id)
    assert not p.btn_reparar.disabled
    p.reparar(None)
    (estado,) = pagina.campos()
    assert estado.value == "BUENO" and [o.key for o in estado.options] == ["BUENO", "REGULAR"]
    pagina.aceptar()
    assert not pagina.dialogos and "reparado" in pagina.ultimo_mensaje()
    assert p.ejemplares[ejemplar.id]["estado_fisico"] == "BUENO"


@pytest.mark.parametrize("titulo, socio, observacion, pago", [
    ("Ficciones", "Gómez, Martín", "Tapa con marcas de uso", "Pagada"),
    ("Don Segundo Sombra", "Torres, Camila", "Llegó con la tapa mojada", "Impaga"),
])
def test_ver_devolucion_con_observacion_y_multa(app, titulo, socio, observacion, pago):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "prestamos")
    elegir(p.filtro, "Devueltos y cancelados")
    prestamo_id = next(i for i, f in p.filas.items() if f["titulo"] == titulo and f["socio"] == socio)
    p.tabla._seleccionar(prestamo_id)
    assert not p.btn_ver_devolucion.disabled
    p.ver_devolucion(None)
    textos = pagina.textos()
    assert observacion in textos and pago in textos
    assert any(x.startswith("Multa de $") for x in textos)
    assert len(pagina.dialogos[-1].actions) == 1             # solo lectura: un único botón "Cerrar"
    pagina.aceptar()
    assert not pagina.dialogos


def test_ver_devolucion_deshabilitado_si_no_esta_devuelto(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "prestamos")
    elegir(p.filtro, "Todos")
    for estado in ("ACTIVO", "CANCELADO"):
        prestamo_id = next(i for i, f in p.filas.items() if f["estado"] == estado)
        p.tabla._seleccionar(prestamo_id)
        assert p.btn_ver_devolucion.disabled, estado
        p.tabla._seleccionar(prestamo_id)                    # deseleccionar


def test_sanciones_del_socio_tienen_un_unico_boton_cerrar(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "socios")
    p.tabla._seleccionar(next(iter(p.filas)))
    p.ver_sanciones(None)
    (cerrar,) = pagina.dialogos[-1].actions
    assert cerrar.content == "Cerrar"


def test_pagar_multa_muestra_el_aviso_dentro_del_dialogo(app):
    aplicacion, pagina = app
    p = pantalla(aplicacion, "socios")
    camila = next(i for i, f in p.filas.items() if f["apellido"] == "Torres")
    p.tabla._seleccionar(camila)
    assert p.filas[camila]["deuda"] > 0
    p.ver_sanciones(None)
    columna = pagina.dialogos[-1].content.content
    btn_pagar, tabla = columna.controls[0], columna.controls[1].content.controls[0].controls[0]
    impaga = next(fila for fila in tabla.rows if fila.cells[-1].content.content.value == "Impaga")
    impaga.on_select_change(None)
    assert not btn_pagar.disabled
    btn_pagar.on_click(None)
    assert pagina.dialogos and pagina.dialogos[-1].data.value == "Pago registrado"   # se ve sobre el modal
    assert not any(f.cells[-1].content.content.value == "Impaga" for f in tabla.rows)
    assert not p.filas[camila]["deuda"]                     # la pantalla de socios también se refrescó
