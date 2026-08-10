"""Importador masivo de planilla ITV (Excel)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.services.itv_excel import apply_import, build_preview, sincronizar_estado_desde_excel
from app.services.empresa_excel_sync import apply_empresa_sync, build_empresa_sync_preview

router = APIRouter(prefix="/importador", tags=["Importador"])

MAX_BYTES = 40 * 1024 * 1024  # 40 MB


async def _read_xlsx(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no válido. Se requiere un archivo .xlsx de Excel.",
        )
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo vacío.")
    if len(contents) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo supera el límite de 40 MB.",
        )
    return contents


@router.post("/preview")
async def preview_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """
    Analiza las hojas General y BAJAS y cruza RUA/chasis con la base
    sin modificar datos.
    """
    contents = await _read_xlsx(file)
    try:
        preview = await build_preview(db, contents)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al analizar el Excel: {exc}",
        ) from exc

    return {
        "status": "preview",
        "filename": file.filename,
        "hoja": preview.hoja,
        "fecha_corte": preview.fecha_corte,
        "total_excel": preview.total_excel,
        "matched_rua": preview.matched_rua,
        "matched_chassis": preview.matched_chassis,
        "matched_total": preview.matched_rua + preview.matched_chassis,
        "solo_excel": preview.solo_excel,
        "solo_db_activos": preview.solo_db_activos,
        "itv_actualizar": preview.itv_actualizar,
        "itv_igual": preview.itv_igual,
        "itv_sin_fecha": preview.itv_sin_fecha,
        "con_seguro_pasajeros": preview.con_seguro_pasajeros,
        "con_seguro_terceros": preview.con_seguro_terceros,
        "tipos_servicio": preview.tipos_servicio,
        "muestra_solo_excel": preview.muestra_solo_excel,
        "muestra_solo_db": preview.muestra_solo_db,
        "muestra_itv_diff": preview.muestra_itv_diff,
        "errores_parseo": preview.errores_parseo,
        "hoja_bajas": preview.hoja_bajas,
        "total_bajas_excel": preview.total_bajas_excel,
        "bajas_a_aplicar": preview.bajas_a_aplicar,
        "bajas_ya_en_db": preview.bajas_ya_en_db,
        "bajas_sin_match_db": preview.bajas_sin_match_db,
        "muestra_bajas": preview.muestra_bajas,
        "mensaje": (
            f"Planilla '{preview.hoja}' con {preview.total_excel} buses. "
            f"{preview.matched_rua + preview.matched_chassis} coinciden con la DB; "
            f"{preview.solo_excel} solo en Excel; "
            f"{preview.itv_actualizar} ITV a actualizar"
            + (
                f"; hoja BAJAS: {preview.bajas_a_aplicar} a dar de baja"
                if preview.hoja_bajas
                else ""
            )
            + "."
        ),
    }


@router.post("/aplicar")
async def aplicar_excel(
    file: UploadFile = File(...),
    sincronizar_estado: str = Form("true"),
    crear_faltantes: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """
    Aplica la planilla: upsert buses/ITV/seguros, aplica BAJAS,
    refresca auxiliar y opcionalmente alinea ACTIVO/INACTIVO con General.
    """
    contents = await _read_xlsx(file)
    sync_estado = str(sincronizar_estado).strip().lower() in ("1", "true", "yes", "si", "sí")
    crear = str(crear_faltantes).strip().lower() in ("1", "true", "yes", "si", "sí")
    usuario = getattr(user, "username", None) or getattr(user, "email", None) or str(user)
    try:
        result = await apply_import(
            db,
            contents,
            sincronizar_estado=sync_estado,
            crear_faltantes=crear,
            usuario=usuario,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al aplicar la importación: {exc}",
        ) from exc

    return {
        "status": "applied",
        "filename": file.filename,
        "buses_creados": result.buses_creados,
        "buses_actualizados": result.buses_actualizados,
        "buses_activados": result.buses_activados,
        "buses_inactivados": result.buses_inactivados,
        "buses_baja": result.buses_baja,
        "itv_insertados": result.itv_insertados,
        "itv_sin_cambio": result.itv_sin_cambio,
        "seguros_insertados": result.seguros_insertados,
        "auxiliar_filas": result.auxiliar_filas,
        "errores": result.errores,
        "mensaje": (
            f"Importación aplicada: {result.buses_actualizados} buses actualizados, "
            f"{result.buses_creados} creados, {result.itv_insertados} ITV nuevas, "
            f"{result.seguros_insertados} seguros"
            + (f", {result.buses_baja} dados de baja" if result.buses_baja else "")
            + "."
        ),
    }


@router.post("/sincronizar-estado")
async def sincronizar_estado_excel(
    file: UploadFile = File(...),
    inactivar_fuera: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """
    Recuperación: alinea ACTIVO/INACTIVO/BAJA según hojas General y BAJAS.
    No toca ITV ni seguros salvo invalidar ITV al dar de baja.
    """
    contents = await _read_xlsx(file)
    inactivar = str(inactivar_fuera).strip().lower() in ("1", "true", "yes", "si", "sí")
    try:
        result = await sincronizar_estado_desde_excel(
            db, contents, inactivar_fuera=inactivar
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar estados: {exc}",
        ) from exc

    return {
        "status": "estado_sincronizado",
        "filename": file.filename,
        "buses_activados": result.buses_activados,
        "buses_inactivados": result.buses_inactivados,
        "buses_baja": result.buses_baja,
        "mensaje": (
            f"Estados alineados: {result.buses_activados} activados, "
            f"{result.buses_inactivados} inactivados, "
            f"{result.buses_baja} dados de baja."
        ),
    }


@router.post("/preview-empresas")
async def preview_empresas_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """
    Cruza EMPRESA-LINEA/CODIGO del Excel con bus_empresa (sin escribir).
    Muestra transferencias y altas necesarias.
    """
    contents = await _read_xlsx(file)
    try:
        preview = await build_empresa_sync_preview(db, contents)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al analizar empresas del Excel: {exc}",
        ) from exc

    return {
        "status": "preview_empresas",
        "filename": file.filename,
        "hoja": preview.hoja,
        "fecha_corte": preview.fecha_corte,
        "total_excel": preview.total_excel,
        "matched_bus": preview.matched_bus,
        "ok_mismo_eot": preview.ok_mismo_eot,
        "a_transferir": preview.a_transferir,
        "a_alta": preview.a_alta,
        "sin_bus": preview.sin_bus,
        "sin_match_eot": preview.sin_match_eot,
        "eot_sin_mapear": preview.eot_sin_mapear,
        "por_eot_destino": preview.por_eot_destino,
        "muestra_transferencias": preview.muestra_transferencias,
        "muestra_altas": preview.muestra_altas,
        "muestra_sin_eot": preview.muestra_sin_eot,
        "errores_parseo": preview.errores_parseo,
        "mensaje": (
            f"Empresas: {preview.a_transferir} transferencias, {preview.a_alta} altas, "
            f"{preview.ok_mismo_eot} ya correctas, {preview.sin_match_eot} sin mapear EOT."
        ),
    }


@router.post("/sincronizar-empresas")
async def sincronizar_empresas_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """
    Alinea bus_empresa con EMPRESA-LINEA del Excel (transferencias / altas).
    No toca ITV ni estado ACTIVO/INACTIVO.
    """
    contents = await _read_xlsx(file)
    usuario = getattr(user, "username", None) or getattr(user, "email", None) or str(user)
    try:
        result = await apply_empresa_sync(db, contents, usuario=usuario)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar empresas: {exc}",
        ) from exc

    return {
        "status": "empresas_sincronizadas",
        "filename": file.filename,
        "transferencias": result.transferencias,
        "altas": result.altas,
        "sin_cambio": result.sin_cambio,
        "omitidos": result.omitidos,
        "errores": result.errores,
        "mensaje": (
            f"Asignaciones: {result.transferencias} transferencias, "
            f"{result.altas} altas, {result.sin_cambio} sin cambio."
        ),
    }


@router.post("/upload-excel")
async def cargar_excel_masivo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Compatibilidad: equivale a /preview."""
    return await preview_excel(file=file, db=db, _user=user)
