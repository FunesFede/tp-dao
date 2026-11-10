"""Conexión a SQLite.

Cada servicio abre su propia conexión con obtener_conexion(), se la pasa a los DAO que necesita
y confirma (commit) o deshace (rollback) la transacción completa. Ver docs/apuntes/acceso-datos.md.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_PREDETERMINADA = RAIZ_PROYECTO / "biblioteca.db"
RUTA_SCHEMA = Path(__file__).resolve().parent / "schema.sql"

_ruta_bd: Path = RUTA_PREDETERMINADA


def configurar_ruta(ruta: str | Path) -> None:
    """Cambia el archivo de base de datos (lo usan las pruebas y el seed)."""
    global _ruta_bd
    _ruta_bd = Path(ruta)


def ruta_actual() -> Path:
    return _ruta_bd


def obtener_conexion() -> sqlite3.Connection:
    conexion = sqlite3.connect(_ruta_bd)
    conexion.row_factory = sqlite3.Row
    # SQLite ignora las claves foráneas si no se activan en cada conexión
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def _tablas_creadas(conexion: sqlite3.Connection) -> bool:
    fila = conexion.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type = 'table' AND name = 'sede'
    """).fetchone()
    return fila[0] > 0


def inicializar_base(reiniciar: bool = False) -> bool:
    """Crea las tablas ejecutando schema.sql.

    Es idempotente: si las tablas ya existen y `reiniciar` es falso, no hace nada.
    Con `reiniciar` borra el archivo y crea la base de cero. Devuelve True si creó las tablas.
    """
    if reiniciar and _ruta_bd.exists():
        _ruta_bd.unlink()
    conexion = obtener_conexion()
    try:
        if _tablas_creadas(conexion):
            return False
        conexion.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))
        conexion.commit()
        return True
    finally:
        conexion.close()
