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
    # Cortar sufijos de línea: "LINEA 5", "LINEAS 53-58", "L-45-56-50"
    s = re.split(r"\bLINEAS?\b", s, maxsplit=1)[0].strip()
    s = re.sub(r"\bL(?:[\s\-]*\d+)+\s*$", "", s).strip()
    s = re.sub(
        r"\b(SRL|SA|S A|S R L|SATC|S A T C|CIA|LTDA|SOCIEDAD ANONIMA)\b",
        " ",
        s,
    )
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


def _build_eot_indexes(
    eots: list[Eot],
) -> tuple[dict[str, Eot], dict[str, list[Eot]], dict[str, list[Eot]]]:
    by_hex: dict[str, Eot] = {}
    by_key: dict[str, list[Eot]] = defaultdict(list)
    by_linea_digits: dict[str, list[Eot]] = defaultdict(list)
    for e in eots:
        if not e.id_eot_vmt_hex:
            continue
        by_hex[e.id_eot_vmt_hex.upper()] = e
        key = _empresa_key(e.eot_nombre)
        if key:
            by_key[key].append(e)
        digits = _linea_digits(e.eot_linea)
        if digits:
            by_linea_digits[digits].append(e)
    return by_hex, by_key, by_linea_digits


def _match_by_name(
    empresa_linea: Optional[str],
    by_key: dict[str, list[Eot]],
) -> list[Eot]:
    key = _empresa_key(empresa_linea)
    if not key:
        return []
    if key in by_key:
        uniq = {e.id_eot_vmt_hex: e for e in by_key[key]}
        if len(uniq) == 1:
            return [next(iter(uniq.values()))]
        if uniq:
            return list(uniq.values())

    candidates: list[tuple[int, Eot]] = []
    for k, lst in by_key.items():
        if not k:
            continue
        if key == k or key.startswith(k + " ") or k.startswith(key + " "):
            for e in lst:
                candidates.append((len(k), e))
        elif len(k) >= 5 and (k in key or key in k):
            for e in lst:
                candidates.append((len(k), e))
    if not candidates:
        return []
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_len = candidates[0][0]
    top = [e for ln, e in candidates if ln == best_len]
    return list({e.id_eot_vmt_hex: e for e in top}.values())


def _disambiguate_by_codigo(candidates: list[Eot], codigo: Optional[int]) -> Optional[Eot]:
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    if codigo is None:
        # Preferir la razón social más específica (nombre más largo)
        candidates = sorted(candidates, key=lambda e: len(e.eot_nombre or ""), reverse=True)
        if len({_empresa_key(e.eot_nombre) for e in candidates}) == 1:
            return candidates[0]
        return None

    cod_s = str(int(codigo))
    scored: list[tuple[int, Eot]] = []
    for e in candidates:
        dig = _linea_digits(e.eot_linea)
        if not dig:
            continue
        if dig == cod_s:
            scored.append((100 + len(dig), e))
        elif len(cod_s) >= 3 and (dig.startswith(cod_s) or cod_s.startswith(dig)):
            scored.append((50 + min(len(dig), len(cod_s)), e))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][0]
    top = [e for sc, e in scored if sc == best]
    uniq = {e.id_eot_vmt_hex: e for e in top}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    return None


def _match_by_codigo(
    codigo: Optional[int],
    by_linea_digits: dict[str, list[Eot]],
    by_hex: dict[str, Eot],
) -> Optional[Eot]:
    if codigo is None:
        return None
    cod_s = str(int(codigo))

    for cand in (cod_s.upper(), cod_s.upper().zfill(4)):
        if cand in by_hex:
            return by_hex[cand]

    exact = by_linea_digits.get(cod_s) or []
    if len({e.id_eot_vmt_hex for e in exact}) == 1:
        return exact[0]

    if len(cod_s) >= 3:
        parcial: list[Eot] = []
        for dig, lst in by_linea_digits.items():
            if len(dig) >= 3 and (dig.startswith(cod_s) or cod_s.startswith(dig)):
                parcial.extend(lst)
        hit = _disambiguate_by_codigo(parcial, codigo)
        if hit:
            return hit
    return None


def _resolve_eot(
    empresa_linea: Optional[str],
    codigo: Optional[int],
    by_key: dict[str, list[Eot]],
    by_linea_digits: dict[str, list[Eot]],
    by_hex: dict[str, Eot],
) -> Optional[Eot]:
    # 1) Nombre (con desambiguación por código si hay varias EOTs "San Isidro…")
    by_name = _match_by_name(empresa_linea, by_key)
    if by_name:
        chosen = _disambiguate_by_codigo(by_name, codigo)
        if chosen:
            return chosen
        if len(by_name) == 1:
            return by_name[0]
    # 2) Solo código / dígitos de línea
    return _match_by_codigo(codigo, by_linea_digits, by_hex)

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

                # Misma fecha de alta: UNIQUE(id_bus, fecha_asignacion) impide
                # cerrar+crear el mismo día → corregir la fila vigente in-place.
                if vigente and vigente.fecha_asignacion == hoy:
                    vigente.id_eot = item.id_eot_destino
                    vigente.motivo = "TRANSFERENCIA"
                    vigente.normativa = "Sync planilla ITV (EMPRESA-LINEA)"
                    vigente.observaciones = f"Excel: {item.excel_empresa}"[:500]
                    vigente.usuario_registro = user
                    vigente.estado_asignacion = "ACTIVA"
                    result.transferencias += 1
                    continue

                if vigente:
                    fin = hoy - timedelta(days=1)
                    if fin < vigente.fecha_asignacion:
                        fin = vigente.fecha_asignacion
                    # Si el fin cae el mismo día que el alta vigente, no se puede
                    # insertar otra fila con la misma fecha_asignacion.
                    if fin == vigente.fecha_asignacion and vigente.fecha_asignacion == hoy:
                        vigente.id_eot = item.id_eot_destino
                        vigente.motivo = "TRANSFERENCIA"
                        vigente.normativa = "Sync planilla ITV (EMPRESA-LINEA)"
                        vigente.observaciones = f"Excel: {item.excel_empresa}"[:500]
                        vigente.usuario_registro = user
                        result.transferencias += 1
                        continue
                    vigente.fecha_fin_asignacion = fin
                    vigente.estado_asignacion = "CERRADA"
                    if not vigente.motivo:
                        vigente.motivo = "TRANSFERENCIA"
                    await db.flush()

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
                await db.flush()
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
    _ = preview
    return result
