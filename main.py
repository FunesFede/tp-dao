"""Punto de entrada de la aplicación.

    python main.py

La primera vez crea la base vacía. Para cargar datos de prueba:

    python -m biblioteca.datos.seed --reiniciar
"""
import flet as ft

from biblioteca.presentacion.app import main

if __name__ == "__main__":
    ft.run(main)
