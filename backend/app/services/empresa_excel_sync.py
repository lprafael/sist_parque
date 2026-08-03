"""Sincroniza bus_empresa según EMPRESA-LINEA / CODIGO de la planilla ITV."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bus, BusEmpresa, Eot
from app.services.itv_excel import ExcelBusRow, parse_general_sheet

MUESTRA_MAX = 25


def _fold(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_s = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_s = ascii_s.upper()
    ascii_s = re.sub(r"[^A-Z0-9]+", " ", ascii_s)
    return re.sub(r"\s+", " ", ascii_s).strip()


def _empresa_key(empresa_linea: Optional[str]) -> str:
    s = _fold(empresa_linea or "")
    if not s:
        return ""
    s = re.split(r"\bLINEAS?\b", s, maxsplit=1)[0].strip()
    s = re.sub(r"\b(SRL|SA|S A|CIA|LTDA|SOCIEDAD ANONIMA)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _linea_digits(eot_linea: Optional[str]) -> str:
    return "".join(re.findall(r"\d+", eot_linea or ""))


def _is_junk_row(r: ExcelBusRow) -> bool:
    rua = (r.rua or "").upper()
    ch = (r.chassis or "").upper()
    if not rua and not ch:
        return True
    if rua.startswith("202") and len(rua) >= 8:
        return True
    if any(x in rua for x in ("ACTUAL", "IMPRES", "TOTAL")):
        return True
    if any(x in ch for x in ("ACTUAL", "IMPRES", "TOTAL")):
        return True
    return False


@dataclass
class EmpresaSyncPreview:
    hoja: str
    fecha_corte: Optional[str]
    total_excel: int = 0
    matched_bus: int = 0
    ok_mismo_eot: int = 0
    a_transferir: int = 0
    a_alta: int = 0
    sin_bus: int = 0
    sin_match_eot: int = 0
    eot_sin_mapear: dict[str, int] = field(default_factory=dict)
    por_eot_destino: dict[str, int] = field(default_factory=dict)
    muestra_transferencias: list[dict] = field(default_factory=list)
    muestra_altas: list[dict] = field(default_factory=list)
    muestra_sin_eot: list[dict] = field(default_factory=list)
    errores_parseo: list[str] = field(default_factory=list)


@dataclass
class EmpresaSyncApplyResult:
    transferencias: int = 0
    altas: int = 0
    sin_cambio: int = 0
    omitidos: int = 0
    errores: list[str] = field(default_factory=list)


@dataclass
class _PlanItem:
    id_bus: int
    rua: str
    chassis: str
    excel_empresa: str
    excel_codigo: Optional[int]
    id_eot_destino: str
    eot_destino_nombre: str
    id_eot_actual: Optional[str]
    eot_actual_nombre: Optional[str]
    accion: str  # ok | transferir | alta


def _build_eot_indexes(eots: list[Eot]) -> tuple[dict[str, Eot], dict[str, list[Eot]], dict[str, Eot]]:
    by_hex: dict[str, Eot] = {}
    by_key: dict[str, list[Eot]] = defaultdict(list)
    by_linea_digits: dict[str, Eot] = {}
    for e in eots:
        if not e.id_eot_vmt_hex:
            continue
        by_hex[e.id_eot_vmt_hex.upper()] = e
        key = _empresa_key(e.eot_nombre)
        if key:
            by_key[key].append(e)
        digits = _linea_digits(e.eot_linea)
        if digits and digits not in by_linea_digits:
            by_linea_digits[digits] = e
    return by_hex, by_key, by_linea_digits


def _resolve_eot(
    empresa_linea: Optional[str],
    codigo: Optional[int],
    by_key: dict[str, list[Eot]],
    by_linea_digits: dict[str, Eot],
    by_hex: dict[str, Eot],
) -> Optional[Eot]:
    if codigo is not None:
        cod_s = str(int(codigo))
        if cod_s in by_linea_digits:
            return by_linea_digits[cod_s]
        # p.ej. Excel 5358 vs eot_linea 53-58-128 → dígitos 5358128
        parcial = [
            e
            for dig, e in by_linea_digits.items()
            if dig.startswith(cod_s) or cod_s.startswith(dig)
        ]
        if len({e.id_eot_vmt_hex for e in parcial}) == 1:
            return parcial[0]
        hex_try = cod_s.upper()
        if hex_try in by_hex:
            return by_hex[hex_try]
        padded = hex_try.zfill(4)
        if padded in by_hex:
            return by_hex[padded]

    key = _empresa_key(empresa_linea)
    if not key:
        return None
    if key in by_key and len(by_key[key]) == 1:
        return by_key[key][0]

    # Contención: preferir la clave EOT más larga que matchee
    candidates: list[tuple[int, Eot]] = []
    for k, lst in by_key.items():
        if not k:
            continue
        if key == k or key.startswith(k) or k.startswith(key) or key in k or k in key:
            for e in lst:
                candidates.append((len(k), e))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_len = candidates[0][0]
    top = [e for ln, e in candidates if ln == best_len]
    # únicos por hex
    uniq = {e.id_eot_vmt_hex: e for e in top}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    return None


async def _load_bus_maps(db: AsyncSession) -> tuple[dict[str, Bus], dict[str, Bus], dict[int, BusEmpresa], dict[str, str]]:
    buses = (await db.execute(select(Bus))).scalars().all()
    rua_map: dict[str, Bus] = {}
    ch_map: dict[str, Bus] = {}
    for b in buses:
        if b.rua:
            rua_map[str(b.rua).strip().upper()] = b
        if b.numero_chassis:
            ch_map[str(b.numero_chassis).strip().upper()] = b

    vigentes = (
        await db.execute(select(BusEmpresa).where(BusEmpresa.fecha_fin_asignacion.is_(None)))
    ).scalars().all()
    vigente_by_bus = {a.id_bus: a for a in vigentes}

    eots = (await db.execute(select(Eot).where(Eot.id_eot_vmt_hex.is_not(None)))).scalars().all()
    eot_nombres = {e.id_eot_vmt_hex: e.eot_nombre for e in eots if e.id_eot_vmt_hex}
    return rua_map, ch_map, vigente_by_bus, eot_nombres


async def _build_plan(db: AsyncSession, file_bytes: bytes) -> tuple[EmpresaSyncPreview, list[_PlanItem], list[Eot]]:
    hoja, fecha_corte, rows, parse_errors = parse_general_sheet(file_bytes)
    preview = EmpresaSyncPreview(hoja=hoja, fecha_corte=fecha_corte, errores_parseo=parse_errors)

    eots = list((await db.execute(select(Eot).where(Eot.id_eot_vmt_hex.is_not(None)))).scalars().all())
    by_hex, by_key, by_linea = _build_eot_indexes(eots)
    rua_map, ch_map, vigente_by_bus, eot_nombres = await _load_bus_maps(db)

    plan_by_bus: dict[int, _PlanItem] = {}
    sin_eot_counter: Counter[str] = Counter()

    for r in rows:
        if _is_junk_row(r):
            continue
        preview.total_excel += 1

        eot = _resolve_eot(r.empresa_linea, r.codigo, by_key, by_linea, by_hex)
        if not eot:
            preview.sin_match_eot += 1
            label = (r.empresa_linea or "").strip() or f"CODIGO={r.codigo}"
            sin_eot_counter[label] += 1
            if len(preview.muestra_sin_eot) < MUESTRA_MAX:
                preview.muestra_sin_eot.append(
                    {
                        "fila": r.row_num,
                        "rua": r.rua,
                        "chassis": r.chassis,
                        "empresa_excel": r.empresa_linea,
                        "codigo": r.codigo,
                    }
                )
            continue

        bus: Optional[Bus] = None
        if r.rua and r.rua in rua_map:
            bus = rua_map[r.rua]
        elif r.chassis and r.chassis in ch_map:
            bus = ch_map[r.chassis]

        if not bus:
            preview.sin_bus += 1
            continue

        preview.matched_bus += 1
        asig = vigente_by_bus.get(bus.id_bus)
        id_actual = asig.id_eot if asig else None
        nombre_actual = eot_nombres.get(id_actual) if id_actual else None

        if id_actual == eot.id_eot_vmt_hex:
            accion = "ok"
            preview.ok_mismo_eot += 1
        elif id_actual:
            accion = "transferir"
            preview.a_transferir += 1
            preview.por_eot_destino[eot.eot_nombre or eot.id_eot_vmt_hex] = (
                preview.por_eot_destino.get(eot.eot_nombre or eot.id_eot_vmt_hex, 0) + 1
            )
        else:
            accion = "alta"
            preview.a_alta += 1
            preview.por_eot_destino[eot.eot_nombre or eot.id_eot_vmt_hex] = (
                preview.por_eot_destino.get(eot.eot_nombre or eot.id_eot_vmt_hex, 0) + 1
            )

        item = _PlanItem(
            id_bus=bus.id_bus,
            rua=bus.rua or (r.rua or ""),
            chassis=bus.numero_chassis or (r.chassis or ""),
            excel_empresa=r.empresa_linea or "",
            excel_codigo=r.codigo,
            id_eot_destino=eot.id_eot_vmt_hex,
            eot_destino_nombre=eot.eot_nombre or eot.id_eot_vmt_hex,
            id_eot_actual=id_actual,
            eot_actual_nombre=nombre_actual,
            accion=accion,
        )
        # última fila del Excel gana si hay duplicados
        plan_by_bus[bus.id_bus] = item

        if accion == "transferir" and len(preview.muestra_transferencias) < MUESTRA_MAX:
            preview.muestra_transferencias.append(
                {
                    "id_bus": item.id_bus,
                    "rua": item.rua,
                    "chassis": item.chassis,
                    "de": item.eot_actual_nombre,
                    "de_hex": item.id_eot_actual,
                    "a": item.eot_destino_nombre,
                    "a_hex": item.id_eot_destino,
                    "empresa_excel": item.excel_empresa,
                }
            )
        elif accion == "alta" and len(preview.muestra_altas) < MUESTRA_MAX:
            preview.muestra_altas.append(
                {
                    "id_bus": item.id_bus,
                    "rua": item.rua,
                    "chassis": item.chassis,
                    "a": item.eot_destino_nombre,
                    "a_hex": item.id_eot_destino,
                    "empresa_excel": item.excel_empresa,
                }
            )

    # Recalcular contadores desde plan único por bus (evita doble conteo Excel)
    preview.ok_mismo_eot = sum(1 for i in plan_by_bus.values() if i.accion == "ok")
    preview.a_transferir = sum(1 for i in plan_by_bus.values() if i.accion == "transferir")
    preview.a_alta = sum(1 for i in plan_by_bus.values() if i.accion == "alta")
    preview.matched_bus = len(plan_by_bus)
    preview.por_eot_destino = dict(
        Counter(
            i.eot_destino_nombre
            for i in plan_by_bus.values()
            if i.accion in ("transferir", "alta")
        )
    )
    preview.eot_sin_mapear = dict(sin_eot_counter.most_common(30))
    return preview, list(plan_by_bus.values()), eots


async def build_empresa_sync_preview(db: AsyncSession, file_bytes: bytes) -> EmpresaSyncPreview:
    preview, _, _ = await _build_plan(db, file_bytes)
    return preview


async def apply_empresa_sync(
    db: AsyncSession,
    file_bytes: bytes,
    *,
    usuario: Optional[str] = None,
    fecha: Optional[date] = None,
) -> EmpresaSyncApplyResult:
    """Cierra asignaciones vigentes incorrectas y crea la del Excel."""
    preview, plan, _ = await _build_plan(db, file_bytes)
    result = EmpresaSyncApplyResult()
    hoy = fecha or date.today()
    user = (usuario or "importador_excel")[:100]

    for item in plan:
        if item.accion == "ok":
            result.sin_cambio += 1
            continue
        if item.accion not in ("transferir", "alta"):
            result.omitidos += 1
            continue
        try:
            async with db.begin_nested():
                vigente = (
                    await db.execute(
                        select(BusEmpresa).where(
                            BusEmpresa.id_bus == item.id_bus,
                            BusEmpresa.fecha_fin_asignacion.is_(None),
                        )
                    )
                ).scalar_one_or_none()

                if vigente and vigente.id_eot == item.id_eot_destino:
                    result.sin_cambio += 1
                    continue

                if vigente:
                    fin = hoy - timedelta(days=1)
                    if fin < vigente.fecha_asignacion:
                        fin = vigente.fecha_asignacion
                    vigente.fecha_fin_asignacion = fin
                    vigente.estado_asignacion = "CERRADA"
                    if not vigente.motivo:
                        vigente.motivo = "TRANSFERENCIA"

                nueva = BusEmpresa(
                    id_bus=item.id_bus,
                    id_eot=item.id_eot_destino,
                    fecha_asignacion=hoy,
                    fecha_fin_asignacion=None,
                    estado_asignacion="ACTIVA",
                    motivo="TRANSFERENCIA" if vigente else "ALTA",
                    normativa="Sync planilla ITV (EMPRESA-LINEA)",
                    observaciones=f"Excel: {item.excel_empresa}"[:500],
                    usuario_registro=user,
                )
                db.add(nueva)
                if vigente:
                    result.transferencias += 1
                else:
                    result.altas += 1
        except Exception as exc:  # noqa: BLE001
            result.errores.append(f"bus {item.id_bus} ({item.rua}): {exc}")
            if len(result.errores) >= 80:
                result.errores.append("… (más errores omitidos)")
                break

    await db.commit()
    # silence unused
    _ = preview
    return result
