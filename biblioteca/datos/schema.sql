PRAGMA foreign_keys = ON;

-- =========================================================
-- Sedes
-- =========================================================
CREATE TABLE sede (
    id          INTEGER PRIMARY KEY,
    nombre      TEXT    NOT NULL UNIQUE,
    direccion   TEXT    NOT NULL,
    telefono    TEXT,
    email       TEXT,
    horario     TEXT,
    activa      INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0, 1)),
    fecha_baja  TEXT,
    -- Política de sanción por atraso (patrón Strategy)
    politica_sancion   TEXT    NOT NULL DEFAULT 'MONETARIA'
                       CHECK (politica_sancion IN ('MONETARIA', 'SUSPENSION')),
    monto_por_dia      REAL    CHECK (monto_por_dia > 0),
    factor_suspension  INTEGER CHECK (factor_suspension > 0),
    CHECK ((activa = 1 AND fecha_baja IS NULL) OR (activa = 0 AND fecha_baja IS NOT NULL)),
    CHECK ((politica_sancion = 'MONETARIA'  AND monto_por_dia     IS NOT NULL) OR
           (politica_sancion = 'SUSPENSION' AND factor_suspension IS NOT NULL))
);

-- =========================================================
-- Socios
-- =========================================================
CREATE TABLE socio (
    id           INTEGER PRIMARY KEY,
    dni          TEXT    NOT NULL UNIQUE,
    nombre       TEXT    NOT NULL,
    apellido     TEXT    NOT NULL,
    email        TEXT    UNIQUE,
    telefono     TEXT,
    sede_id      INTEGER NOT NULL REFERENCES sede(id),      -- sede de alta
    -- Inhabilitado si suspendido_hasta > hoy o inhabilitado_manual = 1
    suspendido_hasta      TEXT,
    inhabilitado_manual   INTEGER NOT NULL DEFAULT 0 CHECK (inhabilitado_manual IN (0, 1)),
    motivo_inhabilitacion TEXT,
    fecha_alta   TEXT    NOT NULL DEFAULT (date('now')),
    CHECK (inhabilitado_manual = 0 OR motivo_inhabilitacion IS NOT NULL)
);

-- =========================================================
-- Catálogo (obra) y ejemplares físicos
-- =========================================================
CREATE TABLE libro (
    id             INTEGER PRIMARY KEY,
    isbn           TEXT    NOT NULL UNIQUE,
    titulo         TEXT    NOT NULL,
    autor          TEXT    NOT NULL,
    editorial      TEXT,
    anio           INTEGER,
    tipo_material  TEXT    NOT NULL DEFAULT 'LIBRO'
                   CHECK (tipo_material IN ('LIBRO', 'REVISTA', 'MAPA', 'MULTIMEDIA', 'OTRO'))
);

CREATE TABLE ejemplar (
    id                 INTEGER PRIMARY KEY,
    libro_id           INTEGER NOT NULL REFERENCES libro(id),
    sede_id            INTEGER NOT NULL REFERENCES sede(id),  -- sede propietaria
    sede_actual_id     INTEGER NOT NULL REFERENCES sede(id),  -- dónde está físicamente
    codigo_inventario  TEXT    NOT NULL UNIQUE,
    estado             TEXT    NOT NULL DEFAULT 'DISPONIBLE'
                       CHECK (estado IN ('DISPONIBLE', 'RESERVADO', 'PRESTADO',
                                         'EN_TRANSITO', 'EXTRAVIADO', 'BAJA')),
    estado_fisico      TEXT    NOT NULL DEFAULT 'BUENO'
                       CHECK (estado_fisico IN ('BUENO', 'REGULAR', 'DANIADO', 'DESTRUIDO'))
);

CREATE INDEX ix_ejemplar_libro_sede ON ejemplar(libro_id, sede_actual_id, estado);

-- =========================================================
-- Préstamos (local e interbibliotecario)
--   LOCAL: origen = destino
--   INTER: el ejemplar sale de la sede origen y se retira en la sede destino
-- =========================================================
CREATE TABLE prestamo (
    id                 INTEGER PRIMARY KEY,
    socio_id           INTEGER NOT NULL REFERENCES socio(id),
    ejemplar_id        INTEGER NOT NULL REFERENCES ejemplar(id),
    tipo               TEXT    NOT NULL CHECK (tipo IN ('LOCAL', 'INTER')),
    sede_origen_id     INTEGER NOT NULL REFERENCES sede(id),
    sede_destino_id    INTEGER NOT NULL REFERENCES sede(id),
    fecha_solicitud    TEXT    NOT NULL DEFAULT (datetime('now')),
    fecha_inicio       TEXT,     -- cuando el socio retira el ejemplar
    fecha_vencimiento  TEXT,
    fecha_devolucion   TEXT,
    estado             TEXT    NOT NULL DEFAULT 'SOLICITADO'
                       CHECK (estado IN ('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO',
                                         'ACTIVO', 'VENCIDO', 'DEVUELTO', 'CANCELADO')),
    CHECK ((tipo = 'LOCAL' AND sede_origen_id =  sede_destino_id) OR
           (tipo = 'INTER' AND sede_origen_id <> sede_destino_id))
);

-- Un ejemplar no puede estar en dos préstamos abiertos a la vez
CREATE UNIQUE INDEX ux_prestamo_abierto_por_ejemplar
    ON prestamo(ejemplar_id)
    WHERE estado IN ('SOLICITADO', 'EN_TRANSITO', 'LISTO_PARA_RETIRO', 'ACTIVO', 'VENCIDO');

-- =========================================================
-- Reservas (sobre la obra, no sobre un ejemplar puntual)
-- =========================================================
CREATE TABLE reserva (
    id                  INTEGER PRIMARY KEY,
    socio_id            INTEGER NOT NULL REFERENCES socio(id),
    libro_id            INTEGER NOT NULL REFERENCES libro(id),
    sede_retiro_id      INTEGER NOT NULL REFERENCES sede(id),
    ejemplar_asignado_id INTEGER REFERENCES ejemplar(id),
    fecha_reserva       TEXT    NOT NULL DEFAULT (datetime('now')),
    fecha_expiracion    TEXT,
    estado              TEXT    NOT NULL DEFAULT 'PENDIENTE'
                        CHECK (estado IN ('PENDIENTE', 'ASIGNADA', 'CUMPLIDA', 'CANCELADA', 'EXPIRADA'))
);

-- Un socio no puede tener dos reservas vigentes del mismo libro
CREATE UNIQUE INDEX ux_reserva_vigente
    ON reserva(socio_id, libro_id)
    WHERE estado IN ('PENDIENTE', 'ASIGNADA');

-- =========================================================
-- Remitos (envíos entre sedes) y su trazabilidad
-- =========================================================
CREATE TABLE remito (
    id               INTEGER PRIMARY KEY,
    numero           TEXT    NOT NULL UNIQUE,
    sede_origen_id   INTEGER NOT NULL REFERENCES sede(id),
    sede_destino_id  INTEGER NOT NULL REFERENCES sede(id),
    estado           TEXT    NOT NULL DEFAULT 'EN_PREPARACION'
                     CHECK (estado IN ('EN_PREPARACION', 'DESPACHADO', 'EN_TRANSITO', 'RECIBIDO',
                                       'RECIBIDO_CON_INCIDENCIA', 'EXTRAVIADO', 'ANULADO')),
    fecha_creacion   TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (sede_origen_id <> sede_destino_id)
);

-- Ejemplares que viajan en el remito. prestamo_id es NULL en envíos de retorno
-- o de reubicación que no están ligados a un préstamo.
CREATE TABLE remito_detalle (
    remito_id         INTEGER NOT NULL REFERENCES remito(id),
    ejemplar_id       INTEGER NOT NULL REFERENCES ejemplar(id),
    prestamo_id       INTEGER REFERENCES prestamo(id),
    estado_recepcion  TEXT CHECK (estado_recepcion IN ('OK', 'DANIADO', 'FALTANTE', 'DESTRUIDO')),
    PRIMARY KEY (remito_id, ejemplar_id)
);

-- Historial de estados: cada transición queda registrada (trazabilidad).
CREATE TABLE remito_movimiento (
    id               INTEGER PRIMARY KEY,
    remito_id        INTEGER NOT NULL REFERENCES remito(id),
    estado_anterior  TEXT,
    estado_nuevo     TEXT    NOT NULL,
    fecha_hora       TEXT    NOT NULL,
    sede_id          INTEGER REFERENCES sede(id),
    observacion      TEXT
);

CREATE INDEX ix_movimiento_remito ON remito_movimiento(remito_id, fecha_hora);

-- =========================================================
-- Devoluciones y multas
-- =========================================================
CREATE TABLE devolucion (
    id                 INTEGER PRIMARY KEY,
    prestamo_id        INTEGER NOT NULL UNIQUE REFERENCES prestamo(id),
    fecha              TEXT    NOT NULL DEFAULT (datetime('now')),
    sede_recepcion_id  INTEGER NOT NULL REFERENCES sede(id),
    estado_fisico      TEXT    NOT NULL
                       CHECK (estado_fisico IN ('BUENO', 'REGULAR', 'DANIADO', 'DESTRUIDO')),
    observaciones      TEXT
);

-- Sanción por atraso, daño o pérdida. Monetaria o suspensión (patrón Strategy).
CREATE TABLE sancion (
    id                INTEGER PRIMARY KEY,
    prestamo_id       INTEGER NOT NULL REFERENCES prestamo(id),
    socio_id          INTEGER NOT NULL REFERENCES socio(id),
    tipo              TEXT    NOT NULL CHECK (tipo IN ('MONETARIA', 'SUSPENSION')),
    motivo            TEXT    NOT NULL CHECK (motivo IN ('ATRASO', 'DANIO', 'PERDIDA')),
    dias_atraso       INTEGER NOT NULL DEFAULT 0 CHECK (dias_atraso >= 0),
    monto             REAL    CHECK (monto >= 0),
    pagada            INTEGER CHECK (pagada IN (0, 1)),
    suspendido_hasta  TEXT,
    fecha             TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (tipo = 'MONETARIA'  AND monto IS NOT NULL AND pagada IS NOT NULL AND suspendido_hasta IS NULL) OR
        (tipo = 'SUSPENSION' AND monto IS NULL     AND pagada IS NULL     AND suspendido_hasta IS NOT NULL)
    )
);

CREATE INDEX ix_sancion_socio ON sancion(socio_id, tipo);
