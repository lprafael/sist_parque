"""
Schemas Pydantic para validación de datos — Sistema de Parque Automotor VMT
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


# ============================================================
# AUTH
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: "UsuarioOut"

class RefreshRequest(BaseModel):
    refresh_token: str


# ============================================================
# USUARIOS
# ============================================================

class UsuarioBase(BaseModel):
    username: str
    email: EmailStr
    nombre_completo: Optional[str] = None
    rol: str = "OPERADOR"  # ADMIN, SUPERVISOR, OPERADOR, CONSULTA

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioUpdate(BaseModel):
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    estado_usuario: Optional[str] = None
    password: Optional[str] = None

class UsuarioOut(UsuarioBase):
    id_usuario: int
    estado_usuario: str
    ultimo_acceso: Optional[datetime] = None
    fecha_registro: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================
# MARCAS / CARROCERÍAS
# ============================================================

# ============================================================
# EMPRESAS (public.eots — READ ONLY)
# ============================================================

class EotOut(BaseModel):
    eot_id: int
    id_eot_vmt_hex: Optional[str] = None
    eot_nombre: Optional[str] = None
    eot_linea: Optional[str] = None          # líneas que opera
    cod_catalogo: Optional[int] = None
    autorizado: Optional[int] = None
    operativo: Optional[int] = None
    reserva: Optional[int] = None
    situacion: Optional[int] = None
    e_mail: Optional[str] = None
    permisionario: Optional[bool] = None

    class Config:
        from_attributes = True


class MarcaOut(BaseModel):
    id_marca: int
    nombre: str
    class Config:
        from_attributes = True

class MarcaCarroceriaOut(BaseModel):
    id_marca_carroceria: int
    nombre: str
    class Config:
        from_attributes = True

class TipoCarroceriaOut(BaseModel):
    id_tipo: int
    descripcion: str
    class Config:
        from_attributes = True

class TipoServicioOut(BaseModel):
    id_tipo_servicio: int
    nombre: str
    descripcion: Optional[str] = None
    activo: Optional[bool] = True
    class Config:
        from_attributes = True

class TipoSeguroOut(BaseModel):
    id_tipo_seguro: int
    nombre: str
    descripcion: Optional[str] = None
    activo: Optional[bool] = True
    class Config:
        from_attributes = True


# ============================================================
# BUSES
# ============================================================

class BusBase(BaseModel):
    numero_orden: Optional[int] = None
    id_marca: Optional[int] = None
    año: int
    numero_chassis: str
    rua: str
    id_tipo_carroceria: Optional[int] = None
    id_marca_carroceria: Optional[int] = None
    id_tipo_servicio: Optional[int] = None
    capacidad_pasajeros: Optional[int] = None
    combustible: Optional[str] = None
    cilindrada: Optional[str] = None
    color: Optional[str] = None
    estado_bus: str = "ACTIVO"
    tiene_rampa: bool = False

class BusCreate(BusBase):
    pass

class BusUpdate(BaseModel):
    numero_orden: Optional[int] = None
    id_marca: Optional[int] = None
    año: Optional[int] = None
    numero_chassis: Optional[str] = None
    rua: Optional[str] = None
    id_tipo_carroceria: Optional[int] = None
    id_marca_carroceria: Optional[int] = None
    id_tipo_servicio: Optional[int] = None
    capacidad_pasajeros: Optional[int] = None
    combustible: Optional[str] = None
    cilindrada: Optional[str] = None
    color: Optional[str] = None
    estado_bus: Optional[str] = None
    tiene_rampa: Optional[bool] = None

class BusBajaIn(BaseModel):
    """Baja formal del parque: estado BAJA + cierra asignación + invalida ITV."""
    fecha_baja: date
    causal: str
    causal_detalle: Optional[str] = None
    normativa: Optional[str] = None
    observaciones: Optional[str] = None

    @field_validator("causal")
    @classmethod
    def causal_valida(cls, v: str) -> str:
        from app.services.bus_baja import CAUSALES_BAJA
        c = (v or "").strip().upper()
        if c not in CAUSALES_BAJA:
            raise ValueError(f"causal inválida. Use: {', '.join(CAUSALES_BAJA)}")
        return c


class BusBajaOut(BaseModel):
    id_bus: int
    estado_bus: str
    fecha_baja: date
    causal: str
    asignacion_cerrada: bool
    itv_invalidadas: int
    bus: "BusOut"


class BusOut(BusBase):
    id_bus: int
    fecha_registro: Optional[datetime] = None
    fecha_modificacion: Optional[datetime] = None
    # Joins
    marca_nombre: Optional[str] = None
    tipo_carroceria_nombre: Optional[str] = None
    marca_carroceria_nombre: Optional[str] = None
    tipo_servicio_nombre: Optional[str] = None
    empresa_actual: Optional[str] = None
    itv_vencimiento: Optional[date] = None
    itv_estado: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# BUS-EMPRESA (Asignaciones históricas bus ↔ EOT)
# ============================================================

MOTIVOS_ASIGNACION = ("ALTA", "TRANSFERENCIA", "BAJA", "SUSPENSION")
TIPOS_DOCUMENTO_EOT = ("HABILITACION", "AUMENTO", "DISMINUCION")

class BusEmpresaBase(BaseModel):
    id_bus: int
    id_eot: str
    fecha_asignacion: date
    fecha_fin_asignacion: Optional[date] = None
    estado_asignacion: str = "ACTIVA"
    motivo: Optional[str] = None
    normativa: Optional[str] = None
    observaciones: Optional[str] = None

class BusEmpresaCreate(BaseModel):
    """Alta o transferencia: siempre crea asignación vigente (fecha_fin=null)."""
    id_bus: int
    id_eot: str
    fecha_asignacion: date
    motivo: Optional[str] = None  # ALTA | TRANSFERENCIA (auto si se omite)
    normativa: Optional[str] = None
    observaciones: Optional[str] = None

class BusEmpresaBaja(BaseModel):
    """Baja o suspensión: cierra la asignación vigente sin pasar a otra EOT."""
    id_bus: int
    fecha_fin: date
    motivo: str = "BAJA"  # BAJA | SUSPENSION
    normativa: Optional[str] = None
    observaciones: Optional[str] = None

class BusEmpresaOut(BusEmpresaBase):
    id_asignacion: int
    usuario_registro: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    empresa_nombre: Optional[str] = None     # viene de public.eots.eot_nombre
    empresa_lineas: Optional[str] = None     # viene de public.eots.eot_linea

    class Config:
        from_attributes = True


# ============================================================
# ITV
# ============================================================

class ItvBusBase(BaseModel):
    id_bus: int
    fecha_itv: date
    fecha_vencimiento: date
    resultado_itv: Optional[str] = None  # TOTAL / PARCIAL
    centro_itv: Optional[str] = None
    numero_certificado: Optional[str] = None
    observaciones: Optional[str] = None
    archivo_certificado_url: Optional[str] = None
    es_vigente: bool = True

class ItvBusCreate(ItvBusBase):
    pass

class ItvBusUpdate(BaseModel):
    fecha_itv: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    resultado_itv: Optional[str] = None
    centro_itv: Optional[str] = None
    numero_certificado: Optional[str] = None
    observaciones: Optional[str] = None
    es_vigente: Optional[bool] = None

class ItvBusOut(ItvBusBase):
    id_itv: int
    es_vigente: bool = True
    fecha_registro: Optional[datetime] = None
    dias_para_vencer: Optional[int] = None
    estado_itv: Optional[str] = None   # VIGENTE / POR_VENCER / VENCIDO
    class Config:
        from_attributes = True

class HistorialItvOut(BaseModel):
    id_historial: int
    id_bus: int
    fecha_vencimiento_anterior: Optional[date] = None
    fecha_itv_actual: Optional[date] = None
    fecha_vencimiento_actual: Optional[date] = None
    diferencia_dias: Optional[int] = None
    observaciones: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    class Config:
        from_attributes = True


# ============================================================
# SEGUROS
# ============================================================

class CompaniaSeguroOut(BaseModel):
    id_compania: int
    nombre: str
    ruc: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    activo: Optional[bool] = None
    class Config:
        from_attributes = True

class CompaniaSeguroCreate(BaseModel):
    nombre: str
    ruc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[EmailStr] = None
    activo: bool = True

class SeguroBusBase(BaseModel):
    id_bus: int
    id_tipo_seguro: int
    id_compania: Optional[int] = None
    numero_poliza: Optional[str] = None
    fecha_inicio: date
    fecha_vencimiento: date
    monto_cobertura: Optional[float] = None
    seguro_vigente: bool = True
    observaciones: Optional[str] = None

class SeguroBusCreate(SeguroBusBase):
    pass

class SeguroBusUpdate(BaseModel):
    id_tipo_seguro: Optional[int] = None
    id_compania: Optional[int] = None
    numero_poliza: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    monto_cobertura: Optional[float] = None
    seguro_vigente: Optional[bool] = None
    observaciones: Optional[str] = None

class SeguroBusOut(SeguroBusBase):
    id_seguro: int
    dias_para_vencer: Optional[int] = None
    estado_calculado: Optional[str] = None  # VIGENTE / POR_VENCER / CRITICO / VENCIDO (derivado de fecha)
    compania_nombre: Optional[str] = None
    tipo_seguro_nombre: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    class Config:
        from_attributes = True


# ============================================================
# DOCUMENTOS
# ============================================================

class DocumentoBusCreate(BaseModel):
    id_bus: int
    tipo_documento: str   # POD, RTD, HABILITACION, TITULO
    nombre_documento: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    observaciones: Optional[str] = None

class DocumentoBusOut(DocumentoBusCreate):
    id_documento: int
    estado_documento: Optional[str] = None
    archivo_url: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    class Config:
        from_attributes = True


class DocumentoEotCreate(BaseModel):
    id_eot: str
    tipo_documento: str  # HABILITACION | AUMENTO | DISMINUCION
    numero_resolucion: Optional[str] = None
    nombre_documento: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vigencia: Optional[date] = None
    cantidad_buses: Optional[int] = None
    archivo_url: Optional[str] = None
    observaciones: Optional[str] = None

class DocumentoEotUpdate(BaseModel):
    tipo_documento: Optional[str] = None
    numero_resolucion: Optional[str] = None
    nombre_documento: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vigencia: Optional[date] = None
    cantidad_buses: Optional[int] = None
    archivo_url: Optional[str] = None
    observaciones: Optional[str] = None

class DocumentoEotOut(DocumentoEotCreate):
    id_documento_eot: int
    usuario_registro: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    empresa_nombre: Optional[str] = None
    class Config:
        from_attributes = True


# ============================================================
# ALERTAS
# ============================================================

class AlertaOut(BaseModel):
    id_alerta: int
    tipo_alerta: Optional[str] = None
    id_bus: Optional[int] = None
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_alerta: Optional[date] = None
    prioridad: Optional[str] = None
    estado_alerta: Optional[str] = None
    fecha_atencion: Optional[datetime] = None
    usuario_atencion: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    bus_rua: Optional[str] = None
    class Config:
        from_attributes = True

class AlertaAtender(BaseModel):
    usuario_atencion: str
    observacion: Optional[str] = None


# ============================================================
# DASHBOARD / KPIs
# ============================================================

class KpiDashboard(BaseModel):
    total_buses: int
    buses_activos: int
    buses_inactivos: int
    itv_vigente: int
    itv_por_vencer: int    # próximos 30 días
    itv_vencido: int
    itv_sin_vigente: int = 0  # activos sin ITV vigente (incluidos en itv_vencido)
    # Seguros por tipo (1 póliza vigente por bus+tipo; histórico excluido)
    seguros_pasajeros_vigentes: int
    seguros_pasajeros_por_vencer: int
    seguros_pasajeros_vencidos: int
    seguros_terceros_vigentes: int
    seguros_terceros_por_vencer: int
    seguros_terceros_vencidos: int
    alertas_criticas: int
    alertas_pendientes: int
    total_empresas: int


# ============================================================
# AUDITORÍA
# ============================================================

class AuditoriaOut(BaseModel):
    id_auditoria: int
    tabla_afectada: Optional[str] = None
    id_registro: Optional[int] = None
    accion: Optional[str] = None
    datos_anteriores: Optional[dict] = None
    datos_nuevos: Optional[dict] = None
    usuario: Optional[str] = None
    fecha_accion: Optional[datetime] = None
    ip_usuario: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# MENSAJES / FEEDBACK
# ============================================================

TIPOS_MENSAJE = ("sugerencia", "ajuste", "soporte", "ampliacion", "otro")


class MensajeCreate(BaseModel):
    mensaje: str
    tipo: str = "soporte"

    @field_validator("mensaje")
    @classmethod
    def mensaje_no_vacio(cls, v: str) -> str:
        texto = (v or "").strip()
        if not texto:
            raise ValueError("El mensaje no puede estar vacío")
        if len(texto) > 4000:
            raise ValueError("El mensaje no puede superar 4000 caracteres")
        return texto

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        t = (v or "soporte").strip().lower()
        if t not in TIPOS_MENSAJE:
            raise ValueError(f"Tipo inválido. Use: {', '.join(TIPOS_MENSAJE)}")
        return t


class MensajeOut(BaseModel):
    id: int
    id_usuario: int
    id_sistema: int
    tipo: str
    mensaje: str
    fecha: datetime
    entrante: bool
    leido: bool
    solucion: bool
    id_padre: Optional[int] = None

    class Config:
        from_attributes = True


# ============================================================
# PAGINACIÓN GENÉRICA
# ============================================================

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List


# ============================================================
# Update forward refs
# ============================================================
TokenResponse.model_rebuild()
BusBajaOut.model_rebuild()
