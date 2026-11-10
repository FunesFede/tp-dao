"""Conversión entre tipos de Python y el texto ISO 8601 que se guarda en SQLite."""
from __future__ import annotations

from datetime import date, datetime


def fecha_a_texto(valor: date | None) -> str | None:
    return valor.isoformat() if valor else None


def fecha_hora_a_texto(valor: datetime | None) -> str | None:
    return valor.strftime("%Y-%m-%d %H:%M:%S") if valor else None


def texto_a_fecha(valor: str | None) -> date | None:
    return date.fromisoformat(valor[:10]) if valor else None


def texto_a_fecha_hora(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None
