from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, buses, itv, seguros, empresas,
    dashboard, alertas, documentos, usuarios,
    auditoria, importador, reportes, mensajes
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(buses.router)
api_router.include_router(itv.router)
api_router.include_router(seguros.router)
api_router.include_router(empresas.router)
api_router.include_router(dashboard.router)
api_router.include_router(alertas.router)
api_router.include_router(documentos.router)
api_router.include_router(usuarios.router)
api_router.include_router(auditoria.router)
api_router.include_router(importador.router)
api_router.include_router(reportes.router)
api_router.include_router(mensajes.router)
