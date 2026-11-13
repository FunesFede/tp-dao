"""Carga datos de prueba.

Los datos se cargan a través de los servicios, con un reloj que avanza por un período de
70 días que termina ayer. Así cada préstamo, remito, reserva y sanción pasa por las mismas
validaciones de negocio que en la aplicación, y las fechas quedan coherentes con "hoy".

Uso:
    python -m biblioteca.datos.seed --reiniciar
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta

from ..modelo import ResultadoRecepcion
from ..servicios import RelojManual, Servicios
from .conexion import inicializar_base, obtener_conexion, ruta_actual
from .repositorios import Repositorios

SEDES = {
    "C": ("Biblioteca Central", "Av. Colón 1250", "0351 421-0001", "central@bibliored.test",
          "Lun a vie 8 a 20 · Sáb 9 a 13", "MONETARIA", 200),
    "N": ("Sede Norte", "Av. Rafael Núñez 4500", "0351 481-0002", "norte@bibliored.test",
          "Lun a vie 9 a 18", "SUSPENSION", 2),
    "S": ("Sede Sur", "Av. Vélez Sarsfield 2900", "0351 464-0003", "sur@bibliored.test",
          "Lun a vie 9 a 19", "MONETARIA", 150),
    "G": ("Sede Güemes", "Belgrano 750", "0351 422-0004", "guemes@bibliored.test",
          "Mar a sáb 10 a 18", "SUSPENSION", 1),
    "A": ("Sede Alta Córdoba", "Jerónimo Luis de Cabrera 900", "0351 471-0005", None,
          "Lun a vie 9 a 17", "MONETARIA", 100),
}

SOCIOS = [  # clave, dni, nombre, apellido, sede de alta
    ("s0", "33100200", "Lucía", "Fernández", "C"),
    ("s1", "35210300", "Martín", "Gómez", "S"),
    ("s2", "30987654", "Valentina", "Ruiz", "N"),
    ("s3", "38123456", "Joaquín", "Sosa", "S"),
    ("s4", "40111222", "Camila", "Torres", "N"),
    ("s5", "29876543", "Mateo", "Díaz", "C"),
    ("s6", "41234567", "Sofía", "Romero", "C"),
    ("s7", "36543210", "Tomás", "Herrera", "S"),
    ("s8", "39456789", "Julieta", "Medina", "C"),
    ("s9", "27345678", "Agustín", "Castro", "G"),
    ("s10", "42345678", "Florencia", "Molina", "S"),
    ("s11", "34567890", "Nicolás", "Ortiz", "N"),
    ("s12", "43456789", "Paula", "Benítez", "G"),   # recién asociada: sin préstamos ni reservas
]

LIBROS = [  # isbn, título, autor, editorial, año, sedes de sus ejemplares[, tipo de material]
    ("9789500000017", "Rayuela", "Julio Cortázar", "Sudamericana", 1963, "CCN"),
    ("9789500000024", "Ficciones", "Jorge Luis Borges", "Emecé", 1944, "CS"),
    ("9789500000031", "El túnel", "Ernesto Sabato", "Sur", 1948, "NS"),
    ("9789500000048", "Cien años de soledad", "Gabriel García Márquez", "Sudamericana", 1967, "CNS"),
    ("9789500000055", "La invención de Morel", "Adolfo Bioy Casares", "Losada", 1940, "C"),
    ("9789500000062", "Martín Fierro", "José Hernández", "Eudeba", 1872, "CNSG"),
    ("9789500000079", "Don Segundo Sombra", "Ricardo Güiraldes", "Losada", 1926, "S"),
    ("9789500000086", "Sobre héroes y tumbas", "Ernesto Sabato", "Sudamericana", 1961, "N"),
    ("9789500000093", "El Aleph", "Jorge Luis Borges", "Losada", 1949, "CN"),
    ("9789500000109", "Bestiario", "Julio Cortázar", "Sudamericana", 1951, "SG"),
    ("9789500000116", "Pedro Páramo", "Juan Rulfo", "Fondo de Cultura Económica", 1955, "NG"),
    ("9789500000123", "La tregua", "Mario Benedetti", "Alfa", 1960, "CS"),
    ("9789500000130", "El amor en los tiempos del cólera", "Gabriel García Márquez", "Oveja Negra", 1985, "S"),
    ("9789500000147", "Facundo", "Domingo F. Sarmiento", "Eudeba", 1845, "CA"),
    ("9789500000154", "Los siete locos", "Roberto Arlt", "Losada", 1929, "NSA"),
    ("9789500000161", "Las venas abiertas de América Latina", "Eduardo Galeano", "Siglo XXI", 1971, "GC"),
    ("9789500000178", "Revista Sur, número 1", "Victoria Ocampo (dir.)", "Sur", 1931, "C", "REVISTA"),
    ("9789500000185", "Mapa vial de la provincia de Córdoba", "Agencia Córdoba Turismo", None, 2019, "CG",
     "MAPA"),
    ("9789500000192", "Borges en su voz (audiolibro)", "Jorge Luis Borges", "Audiolibros del Sur", 2004, "N",
     "MULTIMEDIA"),
    ("9789500000208", "Lotería de palabras (juego didáctico)", "Equipo de Bibliored", None, 2020, "S", "OTRO"),
]

DIAS = 70


class CargaDePrueba:
    def __init__(self, inicio: datetime):
        self.inicio = inicio
        self.reloj = RelojManual(inicio)
        self.s = Servicios(self.reloj)
        self.sede: dict[str, int] = {}
        self.socio: dict[str, int] = {}
        self.libro: dict[str, int] = {}
        self.prestamo: dict[str, int] = {}
        self.reserva: dict[str, int] = {}
        self.eventos: list[tuple[datetime, int, callable]] = []

    # --- utilidades -----------------------------------------------------------
    def en(self, dia: int, hora: str, accion) -> None:
        h, m = map(int, hora.split(":"))
        momento = self.inicio.replace(hour=0, minute=0) + timedelta(days=dia, hours=h, minutes=m)
        self.eventos.append((momento, len(self.eventos), accion))

    def _repos(self) -> tuple:
        cx = obtener_conexion()
        return cx, Repositorios(cx)

    def _ejemplar_prestable(self, titulo: str, sede: str) -> int:
        filas = self.s.catalogo.listar_ejemplares(self.libro[titulo], self.sede[sede], solo_prestables=True)
        if not filas:
            raise RuntimeError(f"Sin ejemplar prestable de {titulo} en {sede}")
        return filas[0]["id"]

    def _remito_de(self, prestamo: str) -> int:
        cx, r = self._repos()
        try:
            p = r.prestamos.obtener_por_id(self.prestamo[prestamo])
            return r.remitos.obtener_en_curso_por_ejemplar(p.ejemplar_id).id
        finally:
            cx.close()

    # --- acciones -------------------------------------------------------------
    def prestar(self, clave: str, socio: str, titulo: str, origen: str, destino: str | None = None):
        def accion():
            ejemplar = self._ejemplar_prestable(titulo, origen)
            p = self.s.prestamos.registrar(self.socio[socio], ejemplar, self.sede[origen],
                                           self.sede[destino or origen])
            self.prestamo[clave] = p.id
        return accion

    def despachar(self, prestamo: str):
        return lambda: self.s.remitos.despachar(self._remito_de(prestamo))

    def transito(self, prestamo: str, observacion: str):
        return lambda: self.s.remitos.registrar_transito(self._remito_de(prestamo), observacion)

    def recibir(self, prestamo: str, incidencias: dict[str, str] | None = None):
        def accion():
            remito = self._remito_de(prestamo)
            mapa = {}
            for clave, resultado in (incidencias or {}).items():
                cx, r = self._repos()
                mapa[r.prestamos.obtener_por_id(self.prestamo[clave]).ejemplar_id] = resultado
                cx.close()
            self.s.remitos.recibir(remito, mapa)
        return accion

    def entregar(self, prestamo: str):
        return lambda: self.s.prestamos.entregar(self.prestamo[prestamo])

    def devolver(self, prestamo: str, sede: str, estado: str = "BUENO", obs: str | None = None):
        return lambda: self.s.prestamos.registrar_devolucion(self.prestamo[prestamo], self.sede[sede], estado, obs)

    def reservar(self, clave: str, socio: str, titulo: str, sede: str):
        def accion():
            self.reserva[clave] = self.s.reservas.crear(self.socio[socio], self.libro[titulo], self.sede[sede]).id
        return accion

    # --- escenario ------------------------------------------------------------
    def preparar(self) -> None:
        s = self.s
        for clave, (nombre, direccion, tel, email, horario, politica, valor) in SEDES.items():
            self.sede[clave] = s.sedes.crear(nombre, direccion, tel, email, horario, politica, valor).id
        for clave, dni, nombre, apellido, sede in SOCIOS:
            correo = f"{nombre}.{apellido}".lower().translate(str.maketrans("áéíóú", "aeiou")) + "@correo.test"
            telefono = f"351 15-{dni[2:5]}-{dni[5:]}"   # celular de Córdoba armado a partir del DNI
            self.socio[clave] = s.socios.crear(dni, nombre, apellido, self.sede[sede], correo, telefono).id
        for isbn, titulo, autor, editorial, anio, sedes, *tipo in LIBROS:
            self.libro[titulo] = s.catalogo.crear_libro(isbn, titulo, autor, editorial, anio, *tipo).id
            for sede in sedes:
                s.catalogo.agregar_ejemplar(self.libro[titulo], self.sede[sede])

    def escenario(self) -> None:
        e = self.en
        # Historial: préstamos locales devueltos en término y con atraso
        e(1, "09:30", self.prestar("L1", "s0", "Rayuela", "C"))
        e(1, "11:00", self.prestar("L2", "s1", "Ficciones", "S"))
        e(1, "12:00", self.prestar("L3", "s2", "El túnel", "N"))
        e(10, "10:00", self.devolver("L1", "C"))
        e(20, "11:00", self.devolver("L2", "S", "REGULAR", "Tapa con marcas de uso"))   # 5 días tarde: multa
        e(22, "10:00", self.devolver("L3", "N"))                                         # 7 días tarde: suspensión

        # Interbibliotecario completo: Central -> Sur, devolución y retorno
        e(2, "10:00", self.prestar("I1", "s3", "Cien años de soledad", "C", "S"))
        e(2, "15:00", self.despachar("I1"))
        e(3, "09:00", self.transito("I1", "Centro de distribución"))
        e(3, "16:30", self.recibir("I1"))
        e(4, "10:00", self.entregar("I1"))
        e(20, "12:00", self.devolver("I1", "S"))
        e(21, "10:00", self.despachar("I1"))
        e(22, "11:00", self.recibir("I1"))

        # Interbibliotecario recibido con daño y devuelto tarde (Sur -> Norte)
        e(5, "10:00", self.prestar("I2", "s4", "Don Segundo Sombra", "S", "N"))
        e(6, "11:00", self.despachar("I2"))
        e(7, "10:00", self.transito("I2", "Centro de distribución"))
        e(8, "15:00", self.recibir("I2", {"I2": ResultadoRecepcion.DANIADO}))
        e(9, "10:00", self.entregar("I2"))
        e(35, "10:00", self.devolver("I2", "N", "DANIADO", "Llegó con la tapa mojada"))
        e(36, "10:00", self.despachar("I2"))
        e(38, "10:00", self.recibir("I2"))

        # Dos préstamos en el mismo remito Norte -> Central: uno llega, el otro falta
        e(8, "10:00", self.prestar("I3", "s5", "Sobre héroes y tumbas", "N", "C"))
        e(8, "10:30", self.prestar("I4", "s6", "Pedro Páramo", "N", "C"))
        e(9, "14:00", self.despachar("I3"))
        e(10, "09:00", self.transito("I3", "Centro de distribución"))
        e(12, "16:00", self.recibir("I3", {"I4": ResultadoRecepcion.FALTANTE}))
        e(13, "10:00", self.entregar("I3"))
        e(30, "10:00", self.devolver("I3", "C"))
        e(31, "10:00", self.despachar("I3"))
        e(32, "10:00", self.transito("I3", "Centro de distribución"))
        e(33, "12:00", self.recibir("I3"))

        # Envío extraviado (Güemes -> Sur)
        e(15, "10:00", self.prestar("I5", "s7", "Las venas abiertas de América Latina", "G", "S"))
        e(16, "10:00", self.despachar("I5"))
        e(17, "10:00", self.transito("I5", "Salida del depósito de Güemes"))
        e(20, "09:00", lambda: self.s.remitos.declarar_extravio(self._remito_de("I5"),
                                                                "No llegó; el transporte no lo encuentra"))

        # Remito anulado antes de salir: cancela el préstamo (Central -> Güemes)
        e(18, "10:00", self.prestar("I6", "s9", "La invención de Morel", "C", "G"))
        e(19, "10:00", lambda: self.s.remitos.anular(self._remito_de("I6"), "El socio desistió del pedido"))

        # Reservas: una se asigna al devolverse el ejemplar y se retira; otra se cancela
        e(24, "10:00", self.prestar("L4", "s0", "La invención de Morel", "C"))
        e(25, "10:00", self.reservar("RV1", "s8", "La invención de Morel", "C"))
        e(26, "10:00", lambda: self.s.socios.pagar_multa(
            next(x["id"] for x in self.s.socios.listar_sanciones(self.socio["s1"]) if x["tipo"] == "MONETARIA")))
        e(27, "10:00", self.reservar("RV2", "s10", "Ficciones", "S"))
        e(28, "10:00", lambda: self.s.reservas.cancelar(self.reserva["RV2"]))
        e(30, "11:00", self.devolver("L4", "C"))
        e(32, "15:00", lambda: self.s.reservas.retirar(self.reserva["RV1"]))

        # Gestión de catálogo, sedes y socios
        e(38, "11:00", self.prestar("L6", "s2", "El túnel", "N"))
        e(40, "10:00", lambda: self.s.catalogo.dar_de_baja_ejemplar(self._ejemplar_prestable("Rayuela", "C")))
        e(40, "11:00", lambda: self.s.sedes.dar_de_baja(self.sede["A"]))
        e(44, "10:00", lambda: self.s.prestamos.registrar_devolucion(
            self._prestamo_activo_de("s8"), self.sede["C"], "BUENO"))
        e(45, "10:00", lambda: self.s.socios.inhabilitar(self.socio["s7"], "Documentación de domicilio pendiente"))

        # Situación actual
        e(50, "10:00", self.prestar("L7", "s1", "Cien años de soledad", "S"))      # vencerá
        e(52, "10:00", self.prestar("L8", "s3", "Martín Fierro", "S"))             # vencerá
        e(60, "10:00", self.prestar("L9", "s0", "Ficciones", "C"))
        e(62, "10:00", self.devolver("L6", "N"))                                   # suspensión vigente
        e(62, "11:00", self.prestar("L10", "s10", "La tregua", "S"))
        e(63, "10:00", self.prestar("I7", "s3", "Sobre héroes y tumbas", "N", "S"))
        e(64, "10:00", self.despachar("I7"))
        e(65, "10:00", self.transito("I7", "Centro de distribución"))
        e(66, "14:00", self.recibir("I7"))                                         # listo para retirar
        e(65, "11:00", self.prestar("L11", "s9", "Bestiario", "G"))
        e(66, "10:00", self.reservar("RV3", "s11", "Bestiario", "G"))              # queda pendiente
        e(67, "10:00", self.prestar("I8", "s5", "El amor en los tiempos del cólera", "S", "C"))
        e(68, "10:00", self.despachar("I8"))
        e(69, "08:00", self.transito("I8", "Centro de distribución"))              # en tránsito
        e(69, "09:00", self.prestar("I9", "s6", "Rayuela", "N", "C"))             # en preparación
        e(69, "09:30", self.reservar("RV4", "s4", "Pedro Páramo", "G"))           # asignada

    def casos_adicionales(self) -> None:
        """Casos que completan todos los estados y reglas de negocio."""
        e = self.en
        # Suspensión ya cumplida: devuelto 3 días tarde en Güemes (1 día por día de atraso)
        e(2, "10:30", self.prestar("L17", "s9", "Martín Fierro", "G"))
        e(19, "11:00", self.devolver("L17", "G"))

        # Devolución destruida: el ejemplar queda dado de baja
        e(20, "10:00", self.prestar("L15", "s5", "Martín Fierro", "C"))
        e(28, "10:00", self.devolver("L15", "C", "DESTRUIDO", "Se mojó por completo en una inundación"))

        # Remito recibido con un ejemplar destruido: el préstamo se cancela (Norte -> Sur)
        e(23, "10:00", self.prestar("I13", "s11", "Cien años de soledad", "N", "S"))
        e(24, "10:00", self.despachar("I13"))
        e(26, "10:00", self.recibir("I13", {"I13": ResultadoRecepcion.DESTRUIDO}))

        # Reparación de un ejemplar devuelto en estado regular
        e(25, "09:00", lambda: self.s.catalogo.reparar_ejemplar(self._ejemplar_prestable("Ficciones", "S"), "BUENO"))

        # Interbibliotecario vencido de una sede con suspensión (Norte -> Central)
        e(30, "09:00", self.prestar("I10", "s4", "Los siete locos", "N", "C"))
        e(31, "10:00", self.despachar("I10"))
        e(33, "10:00", self.recibir("I10"))
        e(34, "10:00", self.entregar("I10"))                                       # vence el día 55

        # Reserva asignada que nadie retiró: expira al procesar los vencimientos
        e(40, "09:00", self.reservar("RV5", "s1", "La tregua", "C"))
        e(47, "08:00", lambda: self.s.procesar_vencimientos())                    # apertura de la aplicación

        # Devolución en otra sede: el ejemplar vuelve a la suya en un remito de retorno
        e(41, "10:00", self.prestar("L13", "s6", "Las venas abiertas de América Latina", "C"))
        e(50, "11:00", self.devolver("L13", "S", "REGULAR", "Hojas subrayadas"))
        e(52, "10:00", self.despachar("L13"))
        e(54, "10:00", self.recibir("L13"))

        # Préstamo local vencido de una sede con suspensión (Norte)
        e(45, "11:00", self.prestar("L12", "s11", "Martín Fierro", "N"))           # vence el día 59

        # Remito de retorno en preparación: el ejemplar espera en Central para volver a Sur
        e(55, "10:00", self.prestar("L14", "s10", "El túnel", "S"))
        e(67, "11:00", self.devolver("L14", "C"))

        # Socio en el límite de préstamos abiertos (s3: L8, I7 y este)
        e(68, "11:00", self.prestar("L16", "s3", "Bestiario", "S"))

        # Remito despachado que todavía no registró tránsito (Central -> Norte)
        e(69, "10:00", self.prestar("I12", "s8", "Facundo", "C", "N"))
        e(69, "15:00", self.despachar("I12"))

    def _prestamo_activo_de(self, socio: str) -> int:
        filas = self.s.prestamos.listar(("ACTIVO", "VENCIDO"))
        return next(f["id"] for f in filas if f["socio_id"] == self.socio[socio])

    def ejecutar(self) -> None:
        self.preparar()
        self.escenario()
        self.casos_adicionales()
        for momento, _, accion in sorted(self.eventos, key=lambda x: (x[0], x[1])):
            self.reloj.fijar(momento)
            accion()
        self.s.procesar_vencimientos()


def cargar_datos_de_prueba(hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    inicio = datetime.combine(hoy - timedelta(days=DIAS), time(8, 0))
    CargaDePrueba(inicio).ejecutar()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea la base y carga datos de prueba.")
    parser.add_argument("--reiniciar", action="store_true", help="borra la base existente antes de cargar")
    args = parser.parse_args()
    creada = inicializar_base(reiniciar=args.reiniciar)
    if not creada:
        print(f"La base {ruta_actual()} ya existe. Use --reiniciar para recrearla con datos de prueba.")
        return
    cargar_datos_de_prueba()
    print(f"Base creada y cargada en {ruta_actual()}")


if __name__ == "__main__":
    main()
