"""Exporta un Reporte a PDF con ReportLab, con su gráfico generado con Matplotlib."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import NOMBRE_RED
from .estructura import Reporte, formatear
from .graficos import AZUL, grafico_png


def exportar_pdf(reporte: Reporte, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ancho_pagina = landscape(A4)
    doc = SimpleDocTemplate(str(ruta), pagesize=ancho_pagina, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=reporte.titulo)
    estilos = getSampleStyleSheet()
    celda = ParagraphStyle("celda", parent=estilos["Normal"], fontSize=8, leading=10)
    encabezado = ParagraphStyle("encabezado", parent=celda, textColor=colors.white, fontName="Helvetica-Bold")

    elementos = [
        Paragraph(f"{NOMBRE_RED} · Sistema de Préstamos Interbibliotecarios", estilos["Normal"]),
        Paragraph(reporte.titulo, estilos["Title"]),
        Paragraph(reporte.descripcion, estilos["Normal"]),
        Paragraph(f"Generado el {reporte.generado:%d/%m/%Y %H:%M}", estilos["Italic"]),
        Spacer(1, 12),
    ]

    if reporte.grafico and any(reporte.grafico.valores):
        elementos += [Image(grafico_png(reporte.grafico), width=16 * cm, height=7.2 * cm), Spacer(1, 10)]

    if not reporte.filas:
        elementos.append(Paragraph("No hay datos para este reporte.", estilos["Normal"]))
    else:
        datos = [[Paragraph(c, encabezado) for c in reporte.columnas]]
        datos += [[Paragraph(formatear(v), celda) for v in fila] for fila in reporte.filas]
        if reporte.totales:
            datos.append([Paragraph(f"<b>{formatear(v)}</b>", celda) for v in reporte.totales])
        # La primera columna (nombres, rutas, títulos) lleva más ancho que las numéricas
        disponible = ancho_pagina[0] - 3 * cm
        resto = len(reporte.columnas) - 1
        anchos = [disponible * 0.26] + [disponible * 0.74 / resto] * resto if resto else [disponible]
        tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if reporte.totales:
            estilo.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dde6ef")))
        tabla.setStyle(TableStyle(estilo))
        elementos.append(tabla)

    for nota in reporte.notas:
        elementos += [Spacer(1, 6), Paragraph(nota, estilos["Italic"])]

    doc.build(elementos)
    return ruta
