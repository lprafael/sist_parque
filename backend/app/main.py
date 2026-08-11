from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import check_db_connection
from app.api.v1 import api_router
from app.tasks.scheduler import start_scheduler, stop_scheduler
from app.services.sistema_logs import auditar_request_http, bind_request, ensure_logs_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"[START] {settings.APP_NAME} v{settings.APP_VERSION} iniciando...")
    db_ok = await check_db_connection()
    print(f"   DB [{settings.DB_SCHEMA}@{settings.DB_HOST}:{settings.DB_PORT}]: {'OK' if db_ok else 'ERROR'}")
    if db_ok:
        await ensure_logs_schema()
    start_scheduler()
    print("   Scheduler de alertas: Activo")
    yield
    # Shutdown
    stop_scheduler()
    print("[STOP] Scheduler detenido. Aplicacion cerrada.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Sistema de Gestión de Parque Automotor
**Viceministerio de Transporte — Paraguay**

API REST para la gestión integral del parque automotor de buses del transporte público.
Desarrollada para el **Departamento de Registro y Habilitación**.

### Módulos disponibles:
- 🚌 **Buses** — CRUD completo con historial de cambios
- 🏢 **Empresas** — Consulta de EOTs desde sistema CID (read-only)
- 🔧 **ITV** — Inspecciones técnicas vehiculares
- 🛡️ **Seguros** — Seguros de pasajeros y terceros
- 🔔 **Alertas** — Notificaciones automáticas de vencimientos
- 📊 **Dashboard** — KPIs en tiempo real
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auditoria_sigpa_middleware(request: Request, call_next):
    """Registra mutaciones en sistema.logs_auditoria (sistema_id=5) si el endpoint no lo hizo."""
    bind_request(request)
    response = await call_next(request)
    try:
        await auditar_request_http(request, response.status_code)
    except Exception as exc:
        print(f"[AUDIT] middleware: {exc}")
    return response

# Routers
app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "sistema": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "estado": "operativo",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "schema": settings.DB_SCHEMA,
    }
