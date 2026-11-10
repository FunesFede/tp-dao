"""Exporta un Reporte a CSV con el módulo estándar csv."""
from __future__ import annotations

import csv
from pathlib import Path

from .estructura import Reporte


def exportar_csv(reporte: Reporte, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig y ";" para que Excel en español lo abra con tildes y columnas correctas
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow(reporte.columnas)
        escritor.writerows(["" if v is None else v for v in fila] for fila in reporte.filas)
        if reporte.totales:
            escritor.writerow(["" if v is None else v for v in reporte.totales])
    return ruta
