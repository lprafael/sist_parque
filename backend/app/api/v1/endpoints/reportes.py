import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Bus

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/buses/excel")
async def exportar_buses_excel(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    """Generar y descargar hoja de cálculo Excel con todos los vehículos registrados."""
    q = (
        select(Bus)
        .options(
            selectinload(Bus.marca),
            selectinload(Bus.tipo_carroceria),
            selectinload(Bus.marca_carroceria)
        )
        .order_by(Bus.id_bus.asc())
    )
    res = await db.execute(q)
    buses = res.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Parque Automotor VMT"

    # Estilos cabecera
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = [
        "N° ID", "N° Orden", "RUA / Placa", "Chasis", "Año",
        "Marca", "Tipo Carrocería", "Marca Carrocería", "Combustible", "Estado"
    ]
    ws.append(headers)

    # Formato cabecera
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    # Filas de datos
    for b in buses:
        row = [
            b.id_bus,
            b.numero_orden or "-",
            b.rua or "-",
            b.numero_chassis or "-",
            b.año or "-",
            b.marca.nombre if b.marca else "-",
            b.tipo_carroceria.descripcion if b.tipo_carroceria else "-",
            b.marca_carroceria.nombre if b.marca_carroceria else "-",
            b.combustible or "-",
            b.estado_bus or "-"
        ]
        ws.append(row)

    # Ajuste ancho de columnas
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    headers_resp = {
        'Content-Disposition': 'attachment; filename="Parque_Automotor_VMT.xlsx"'
    }
    return StreamingResponse(
        stream,
        headers=headers_resp,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
