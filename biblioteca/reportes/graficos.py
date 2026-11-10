"""Gráficos de los reportes con Matplotlib.

Se dibujan en memoria (backend Agg) y se devuelven como PNG: el exportador PDF los inserta con
ReportLab y la pantalla de reportes los muestra con ft.Image.
"""
from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")   # sin ventana: el gráfico se dibuja en memoria
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from .estructura import Grafico  # noqa: E402

AZUL = "#1f4e79"
PALETA = ["#2a6f97", "#c46d2a", "#5b8c5a", "#8c5a8c", "#b0a030", "#607080"]


def grafico_png(grafico: Grafico) -> BytesIO:
    figura, eje = plt.subplots(figsize=(8, 3.6), dpi=150)
    etiquetas = [e if len(e) <= 32 else e[:30] + "…" for e in grafico.etiquetas]
    if grafico.tipo == "torta":
        datos = [(e, v) for e, v in zip(etiquetas, grafico.valores) if v]
        eje.pie([v for _, v in datos], labels=[e for e, _ in datos], autopct="%1.0f%%",
                colors=PALETA[:len(datos)], startangle=90, wedgeprops={"edgecolor": "white"})
        eje.axis("equal")
    elif grafico.tipo == "barras_h":
        posiciones = range(len(etiquetas))[::-1]
        eje.barh(list(posiciones), grafico.valores, color=PALETA[0])
        eje.set_yticks(list(posiciones), etiquetas, fontsize=8)
        eje.set_xlabel(grafico.eje_valores)
        eje.spines[["top", "right"]].set_visible(False)
    else:
        eje.bar(etiquetas, grafico.valores, color=PALETA[0])
        eje.set_ylabel(grafico.eje_valores)
        eje.tick_params(axis="x", labelsize=8)
        eje.spines[["top", "right"]].set_visible(False)
    if grafico.tipo != "torta" and all(float(v).is_integer() for v in grafico.valores):
        eje_numerico = eje.xaxis if grafico.tipo == "barras_h" else eje.yaxis
        eje_numerico.set_major_locator(MaxNLocator(integer=True))
    eje.set_title(grafico.titulo, fontsize=10)
    figura.tight_layout()
    buffer = BytesIO()
    figura.savefig(buffer, format="png")
    plt.close(figura)
    buffer.seek(0)
    return buffer
