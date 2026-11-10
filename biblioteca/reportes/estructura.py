"""Estructura de datos de un reporte.

ServicioReportes la produce; la pantalla de reportes y los exportadores la consumen.
Así el mismo reporte se muestra en pantalla, en PDF y en CSV sin volver a consultar la base.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Grafico:
    tipo: str                 # "barras", "barras_h" o "torta"
    titulo: str
    etiquetas: list[str]
    valores: list[float]
    eje_valores: str = ""


@dataclass
class Reporte:
    clave: str
    titulo: str
    descripcion: str
    columnas: list[str]
    filas: list[list]
    generado: datetime
    grafico: Grafico | None = None
    totales: list | None = None
    notas: list[str] = field(default_factory=list)


def formatear(valor) -> str:
    """Texto para mostrar una celda en pantalla o en el PDF."""
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(valor, int):
        return f"{valor:,}".replace(",", ".")
    texto = str(valor)
    # Fechas ISO a formato local
    if len(texto) >= 10 and texto[4] == "-" and texto[7] == "-":
        fecha = f"{texto[8:10]}/{texto[5:7]}/{texto[0:4]}"
        return fecha + (f" {texto[11:16]}" if len(texto) >= 16 else "")
    return texto
