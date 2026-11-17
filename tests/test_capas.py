"""La regla de capas del README: la interfaz solo usa servicios y el modelo no conoce la base."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "biblioteca"


def importa(carpeta: str, modulo: str) -> list[str]:
    patron = re.compile(rf"^\s*(from|import)\s+(\.+|biblioteca\.){modulo}\b", re.MULTILINE)
    return [str(r.relative_to(RAIZ)) for r in (RAIZ / carpeta).rglob("*.py") if patron.search(r.read_text("utf-8"))]


def test_la_interfaz_no_usa_la_capa_de_datos():
    assert importa("presentacion", "datos") == []


def test_el_modelo_no_conoce_la_base_ni_la_interfaz():
    assert importa("modelo", "datos") == [] and importa("modelo", "presentacion") == []
    sqlite = re.compile(r"^\s*(from|import)\s+sqlite3\b", re.MULTILINE)
    assert not [r for r in (RAIZ / "modelo").rglob("*.py") if sqlite.search(r.read_text("utf-8"))]
