"""Excepciones del dominio.

Los mensajes están pensados para mostrarse tal cual en la interfaz.
"""


class ErrorNegocio(Exception):
    """Se viola una regla de negocio (validación, dato inválido, operación no permitida)."""


class TransicionInvalida(ErrorNegocio):
    """Se pidió una operación que el estado actual de un objeto no admite (patrón State)."""
