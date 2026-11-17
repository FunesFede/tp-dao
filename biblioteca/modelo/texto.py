"""Comparación de textos para las búsquedas: sin distinguir mayúsculas, tildes ni signos."""
from __future__ import annotations

import re
import unicodedata


def normalizar(texto: str | None) -> str:
    """«Herrera, Tomás» → «herrera tomas». La ñ queda como n."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w]+", " ", sin_tildes.casefold()).split())


def coincide(busqueda: str | None, texto: str | None) -> bool:
    """Cada palabra de la búsqueda aparece en el texto, en cualquier orden. Sin palabras, coincide todo."""
    objetivo = normalizar(texto)
    return all(palabra in objetivo for palabra in normalizar(busqueda).split())
