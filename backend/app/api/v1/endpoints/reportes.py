import io
from datetime import date
from typing import Optional, List, Dict, Any, Callable

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Bus, ItvBus, BusEmpresa, Eot
from app.api.v1.endpoints.buses import calcular_estado_itv

router = APIRouter(prefix="/reportes", tags=["Reportes"])

# ── Campos exportables ─────────────────────────────────────
CAMPOS: Dict[str, Dict[str, Any]] = {
    "id_bus":              {"label": "N° ID",              "default": True},
    "numero_orden":        {"label": "N° Orden",           "default": True},
    "rua":                 {"label": "RUA / Placa",        "default": True},
    "numero_chassis":      {"label": "Chasis",             "default": True},
    "año":                 {"label": "Año",                "default": True},
    "antiguedad":          {"label": "Antigüedad (años)",  "default": False},
    "marca":               {"label": "Marca",              "default": True},
    "tipo_carroceria":     {"label": "Tipo Carrocería",    "default": True},
    "marca_carroceria":    {"label": "Marca Carrocería",   "default": True},
    "empresa":             {"label": "Empresa",            "default": True},
    "combustible":         {"label": "Combustible",        "default": True},
    "capacidad_pasajeros": {"label": "Capacidad",          "default": False},
    "cilindrada":          {"label": "Cilindrada",         "default": False},
    "color":               {"label": "Color",              "default": False},
    "tipo_servicio":       {"label": "Tipo Servicio",      "default": False},
    "estado_bus":          {"label": "Estado Bus",         "default": True},
    "itv_vencimiento":     {"label": "ITV Vencimiento",    "default": True},
    "itv_estado":          {"label": "Estado ITV",         "default": True},
    "fecha_itv":           {"label": "Fecha ITV",          "default": False},
}

# ── Resúmenes disponibles ──────────────────────────────────
RESUMENES: Dict[str, Dict[str, Any]] = {
    "total":                {"label": "Cantidad total de buses",          "default": True},
    "promedio_antiguedad":  {"label": "Promedio de antigüedad",           "default": True},
    "antiguedad_max":       {"label": "Antigüedad máxima",                "default": True},
    "antiguedad_min":       {"label": "Antigüedad mínima",                "default": False},
    "itv_vencido":          {"label": "Buses con ITV vencido",            "default": True},
    "itv_por_vencer":       {"label": "Buses con ITV por vencer",         "default": True},
    "itv_critico":          {"label": "Buses con ITV crítico",            "default": False},
    "itv_vigente":          {"label": "Buses con ITV vigente",            "default": False},
    "sin_itv":              {"label": "Buses sin ITV",                    "default": False},
    "activos":              {"label": "Buses activos",                    "default": False},
    "inactivos":            {"label": "Buses inactivos",                  "default": False},
}


def _parse_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _valor_campo(row: Dict[str, Any], key: str) -> Any:
    val = row.get(key)
    if val is None or val == "":
        return "-"
    if key == "itv_vencimiento" and hasattr(val, "isoformat"):
        return val.isoformat()
    if key == "fecha_itv" and hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def _calcular_resumenes(rows: List[Dict[str, Any]], keys: List[str]) -> List[tuple]:
    anio_actual = date.today().year
    antiguedades = [anio_actual - r["año"] for r in rows if r.get("año")]
    estados = [r.get("itv_estado") for r in rows]

    calculators: Dict[str, Callable[[], Any]] = {
        "total":               lambda: len(rows),
        "promedio_antiguedad": lambda: round(sum(antiguedades) / len(antiguedades), 1) if antiguedades else 0,
        "antiguedad_max":      lambda: max(antiguedades) if antiguedades else 0,
        "antiguedad_min":      lambda: min(antiguedades) if antiguedades else 0,
        "itv_vencido":         lambda: sum(1 for e in estados if e == "VENCIDO"),
        "itv_por_vencer":      lambda: sum(1 for e in estados if e == "POR_VENCER"),
        "itv_critico":         lambda: sum(1 for e in estados if e == "CRITICO"),
        "itv_vigente":         lambda: sum(1 for e in estados if e == "VIGENTE"),
        "sin_itv":             lambda: sum(1 for e in estados if e == "SIN_ITV"),
        "activos":             lambda: sum(1 for r in rows if (r.get("estado_bus") or "").upper() == "ACTIVO"),
        "inactivos":           lambda: sum(1 for r in rows if (r.get("estado_bus") or "").upper() == "INACTIVO"),
    }

    result = []
    for key in keys:
        if key in RESUMENES and key in calculators:
            label = RESUMENES[key]["label"]
            value = calculators[key]()
            if key in ("promedio_antiguedad", "antiguedad_max", "antiguedad_min"):
                value = f"{value} años"
            result.append((label, value))
    return result


@router.get("/opciones")
async def opciones_reporte(_=Depends(get_current_user)):
    """Catálogo de campos y resúmenes disponibles para el constructor de reportes."""
    return {
        "campos": [
            {"key": k, "label": v["label"], "default": v["default"]}
            for k, v in CAMPOS.items()
        ],
        "resumenes": [
            {"key": k, "label": v["label"], "default": v["default"]}
            for k, v in RESUMENES.items()
        ],
    }


@router.get("/buses/excel")
async def exportar_buses_excel(
    empresas: Optional[str] = Query(None, description="IDs de empresa (hex) separados por coma"),
    estado_bus: Optional[str] = None,
    estado_itv: Optional[str] = None,
    id_marca: Optional[int] = None,
    tipo_servicio: Optional[str] = None,
    año_desde: Optional[int] = None,
    año_hasta: Optional[int] = None,
    campos: Optional[str] = Query(None, description="Claves de campos separadas por coma"),
    resumenes: Optional[str] = Query(None, description="Claves de resúmenes separadas por coma"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Generar Excel personalizado según filtros, campos y resúmenes seleccionados."""
    empresas_ids = _parse_list(empresas)
    campos_sel = _parse_list(campos) or [k for k, v in CAMPOS.items() if v["default"]]
    campos_sel = [c for c in campos_sel if c in CAMPOS]
    if not campos_sel:
        campos_sel = [k for k, v in CAMPOS.items() if v["default"]]

    resumenes_sel = _parse_list(resumenes)
    resumenes_sel = [r for r in resumenes_sel if r in RESUMENES]

    q = (
        select(Bus)
        .options(
            selectinload(Bus.marca),
            selectinload(Bus.tipo_carroceria),
            selectinload(Bus.marca_carroceria),
            selectinload(Bus.itv_registros),
            selectinload(Bus.asignaciones),
        )
    )

    filters = []
    if estado_bus:
        filters.append(Bus.estado_bus == estado_bus.upper())
    if id_marca:
        filters.append(Bus.id_marca == id_marca)
    if tipo_servicio:
        filters.append(Bus.tipo_servicio.ilike(f"%{tipo_servicio}%"))
    if año_desde is not None:
        filters.append(Bus.año >= año_desde)
    if año_hasta is not None:
        filters.append(Bus.año <= año_hasta)
    if empresas_ids:
        subq = (
            select(BusEmpresa.id_bus)
            .where(
                BusEmpresa.estado_asignacion == "ACTIVA",
                BusEmpresa.id_eot.in_(empresas_ids),
            )
        )
        filters.append(Bus.id_bus.in_(subq))

    if filters:
        q = q.where(and_(*filters))

    q = q.order_by(Bus.numero_orden.asc().nulls_last(), Bus.id_bus.asc())
    buses = (await db.execute(q)).scalars().all()

    # Mapa id_eot → nombre
    eot_ids = set()
    for b in buses:
        for a in b.asignaciones:
            if a.estado_asignacion == "ACTIVA":
                eot_ids.add(a.id_eot)

    eot_nombres: Dict[str, str] = {}
    if eot_ids:
        eot_rows = (
            await db.execute(
                select(Eot.id_eot_vmt_hex, Eot.eot_nombre).where(Eot.id_eot_vmt_hex.in_(eot_ids))
            )
        ).all()
        eot_nombres = {r[0]: r[1] for r in eot_rows}

    anio_actual = date.today().year
    rows: List[Dict[str, Any]] = []

    for b in buses:
        itvs = sorted(
            b.itv_registros,
            key=lambda x: x.fecha_vencimiento or date.min,
            reverse=True,
        )
        itv = next((i for i in itvs if i.es_vigente), None) or (itvs[0] if itvs else None)
        venc = itv.fecha_vencimiento if itv else None
        estado = calcular_estado_itv(venc)

        if estado_itv and estado != estado_itv.upper():
            continue

        asig = next((a for a in b.asignaciones if a.estado_asignacion == "ACTIVA"), None)
        empresa_nombre = "-"
        if asig:
            empresa_nombre = eot_nombres.get(asig.id_eot) or asig.id_eot or "-"

        rows.append({
            "id_bus": b.id_bus,
            "numero_orden": b.numero_orden or "-",
            "rua": b.rua or "-",
            "numero_chassis": b.numero_chassis or "-",
            "año": b.año or "-",
            "antiguedad": (anio_actual - b.año) if b.año else "-",
            "marca": b.marca.nombre if b.marca else "-",
            "tipo_carroceria": b.tipo_carroceria.descripcion if b.tipo_carroceria else "-",
            "marca_carroceria": b.marca_carroceria.nombre if b.marca_carroceria else "-",
            "empresa": empresa_nombre,
            "combustible": b.combustible or "-",
            "capacidad_pasajeros": b.capacidad_pasajeros if b.capacidad_pasajeros is not None else "-",
            "cilindrada": b.cilindrada or "-",
            "color": b.color or "-",
            "tipo_servicio": b.tipo_servicio or "-",
            "estado_bus": b.estado_bus or "-",
            "itv_vencimiento": venc,
            "itv_estado": estado,
            "fecha_itv": itv.fecha_itv if itv else None,
        })

    # ── Excel ──────────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Parque Automotor VMT"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")
    border_thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    resumen_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    resumen_title_font = Font(name="Calibri", size=12, bold=True, color="1E3A8A")
    resumen_label_font = Font(name="Calibri", size=11, bold=True)
    resumen_value_font = Font(name="Calibri", size=11)

    headers = [CAMPOS[c]["label"] for c in campos_sel]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center
        cell.border = border_thin

    for row_data in rows:
        values = [_valor_campo(row_data, c) for c in campos_sel]
        ws.append(values)

    data_end = ws.max_row

    for row in ws.iter_rows(min_row=2, max_row=data_end, max_col=len(headers)):
        for cell in row:
            cell.border = border_thin
            cell.alignment = align_center

    # Resúmenes al final
    if resumenes_sel:
        start = data_end + 2
        ws.cell(row=start, column=1, value="RESUMEN DEL REPORTE").font = resumen_title_font

        resumen_rows = _calcular_resumenes(rows, resumenes_sel)
        for i, (label, value) in enumerate(resumen_rows):
            r = start + 1 + i
            cell_l = ws.cell(row=r, column=1, value=label)
            cell_v = ws.cell(row=r, column=2, value=value)
            cell_l.font = resumen_label_font
            cell_v.font = resumen_value_font
            cell_l.fill = resumen_fill
            cell_v.fill = resumen_fill
            cell_l.border = border_thin
            cell_v.border = border_thin

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        headers={"Content-Disposition": 'attachment; filename="Parque_Automotor_VMT.xlsx"'},
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
