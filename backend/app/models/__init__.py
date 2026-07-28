"""
Modelos ORM SQLAlchemy — mapeados al schema registro_habilitacion de PostgreSQL.
Tablas existentes: usuarios, buses, marcas, marcas_carroceria, tipos_carroceria,
bus_empresa, itv_bus, historial_itv, seguros_bus, companias_seguros,
documentos_bus, alertas, auditoria, auxiliar
"""

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean,
    Numeric, Text, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import relationship
from app.core.database import Base


SCHEMA = "registro_habilitacion"


# ============================================================
# AUTENTICACIÓN CENTRALIZADA (schema "sistema")
# ============================================================

class Organismo(Base):
    __tablename__ = "organismos"
    __table_args__ = {"schema": "sistema"}

    id = Column(Integer, primary_key=True, index=True)
    sigla = Column(String(20), nullable=False, unique=True)
    nombre_completo = Column(String(200), nullable=False)
    activo = Column(Boolean, default=True)


class SistemaApp(Base):
    __tablename__ = "sistemas"
    __table_args__ = {"schema": "sistema"}

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(String(200))
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=func.now())

    habilitaciones = relationship("UsuarioSistemaRol", back_populates="sistema")


class Rol(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "sistema"}

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, index=True, nullable=False)
    descripcion = Column(String(200))
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=func.now())

    habilitaciones_usuarios = relationship("UsuarioSistemaRol", back_populates="rol")


class UsuarioSistemaRol(Base):
    __tablename__ = "usuario_sistema_rol"
    __table_args__ = {"schema": "sistema"}

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("sistema.usuarios.id"), nullable=False)
    sistema_id = Column(Integer, ForeignKey("sistema.sistemas.id"), nullable=False)
    rol_id = Column(Integer, ForeignKey("sistema.roles.id"), nullable=False)
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=func.now())

    usuario = relationship("Usuario", back_populates="habilitaciones_sistemas")
    sistema = relationship("SistemaApp", back_populates="habilitaciones")
    rol = relationship("Rol", back_populates="habilitaciones_usuarios")


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "sistema"}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre_completo = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=func.now())
    ultimo_acceso = Column(DateTime)
    creado_por = Column(Integer, ForeignKey("sistema.usuarios.id"), nullable=True)
    id_organismo = Column(Integer, ForeignKey("sistema.organismos.id"), nullable=True)

    habilitaciones_sistemas = relationship("UsuarioSistemaRol", back_populates="usuario")
    organismo = relationship("Organismo")

    # Propiedades de compatibilidad
    @property
    def id_usuario(self) -> int:
        return self.id

    @property
    def password_hash(self) -> str:
        return self.hashed_password

    @property
    def estado_usuario(self) -> str:
        return "ACTIVO" if self.activo else "INACTIVO"

    @property
    def fecha_registro(self) -> DateTime:
        return self.fecha_creacion


class LogAcceso(Base):
    __tablename__ = "logs_acceso"
    __table_args__ = {"schema": "sistema"}

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("sistema.usuarios.id"), nullable=True)
    username = Column(String(50), nullable=False)
    accion = Column(String(50), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    fecha = Column(DateTime, default=func.now())
    detalles = Column(JSONB)
    exitoso = Column(Boolean, default=True)


class Marca(Base):
    __tablename__ = "marcas"
    __table_args__ = {"schema": SCHEMA}

    id_marca = Column(Integer, primary_key=True, index=True)
    nombre   = Column(String(100), nullable=False, unique=True)

    buses = relationship("Bus", back_populates="marca")


class MarcaCarroceria(Base):
    __tablename__ = "marcas_carroceria"
    __table_args__ = {"schema": SCHEMA}

    id_marca_carroceria = Column(Integer, primary_key=True, index=True)
    nombre              = Column(String(100), nullable=False, unique=True)

    buses = relationship("Bus", back_populates="marca_carroceria")


class TipoCarroceria(Base):
    __tablename__ = "tipos_carroceria"
    __table_args__ = {"schema": SCHEMA}

    id_tipo     = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(100), nullable=False)

    buses = relationship("Bus", back_populates="tipo_carroceria")


class Bus(Base):
    __tablename__ = "buses"
    __table_args__ = {"schema": SCHEMA}

    id_bus              = Column(Integer, primary_key=True, index=True)
    numero_orden        = Column(Integer)
    id_marca            = Column(Integer, ForeignKey(f"{SCHEMA}.marcas.id_marca"))
    año                 = Column(Integer, nullable=False)
    numero_chassis      = Column(String(50), unique=True, nullable=False, index=True)
    rua                 = Column(String(20), unique=True, nullable=False, index=True)
    id_tipo_carroceria  = Column(Integer, ForeignKey(f"{SCHEMA}.tipos_carroceria.id_tipo"))
    id_marca_carroceria = Column(Integer, ForeignKey(f"{SCHEMA}.marcas_carroceria.id_marca_carroceria"))
    capacidad_pasajeros = Column(Integer)
    combustible         = Column(String(50))
    cilindrada          = Column(String(20))
    color               = Column(String(50))
    tipo_servicio       = Column(String(50))
    estado_bus          = Column(String(20), default="ACTIVO")
    fecha_registro      = Column(DateTime, default=func.now())
    fecha_modificacion  = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relaciones
    marca           = relationship("Marca", back_populates="buses")
    tipo_carroceria = relationship("TipoCarroceria", back_populates="buses")
    marca_carroceria = relationship("MarcaCarroceria", back_populates="buses")
    asignaciones    = relationship("BusEmpresa", back_populates="bus")
    itv_registros   = relationship("ItvBus", back_populates="bus")
    historial_itv   = relationship("HistorialItv", back_populates="bus")
    seguros         = relationship("SeguroBus", back_populates="bus")
    documentos      = relationship("DocumentoBus", back_populates="bus")
    alertas         = relationship("Alerta", back_populates="bus")


class BusEmpresa(Base):
    """Asignación histórica bus ↔ empresa operadora (id_eot del CID)."""
    __tablename__ = "bus_empresa"
    __table_args__ = {"schema": SCHEMA}

    id_asignacion       = Column(Integer, primary_key=True, index=True)
    id_bus              = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"), nullable=False)
    id_eot              = Column(String(255), nullable=False)   # ID en sistema CID/GTFS
    fecha_asignacion    = Column(Date, nullable=False)
    fecha_fin_asignacion = Column(Date)
    estado_asignacion   = Column(String(20), default="ACTIVA")
    observaciones       = Column(Text)
    usuario_registro    = Column(String(100))
    fecha_registro      = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="asignaciones")


class ItvBus(Base):
    """Inspección Técnica Vehicular — registro actual."""
    __tablename__ = "itv_bus"
    __table_args__ = {"schema": SCHEMA}

    id_itv                  = Column(Integer, primary_key=True, index=True)
    id_bus                  = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"))
    fecha_itv               = Column(Date, nullable=False)
    fecha_vencimiento       = Column(Date, nullable=False, index=True)
    resultado_itv           = Column(String(20))   # TOTAL / PARCIAL
    centro_itv              = Column(String(200))
    numero_certificado      = Column(String(100))
    observaciones           = Column(Text)
    archivo_certificado_url = Column(String(500))
    fecha_registro          = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="itv_registros")


class HistorialItv(Base):
    """Historial de cambios de ITV (diferencias entre períodos)."""
    __tablename__ = "historial_itv"
    __table_args__ = {"schema": SCHEMA}

    id_historial                = Column(Integer, primary_key=True, index=True)
    id_bus                      = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"))
    fecha_vencimiento_anterior  = Column(Date)
    fecha_itv_actual            = Column(Date)
    fecha_vencimiento_actual    = Column(Date)
    diferencia_dias             = Column(Integer)
    observaciones               = Column(Text)
    fecha_registro              = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="historial_itv")


class CompaniaSeguro(Base):
    __tablename__ = "companias_seguros"
    __table_args__ = {"schema": SCHEMA}

    id_compania  = Column(Integer, primary_key=True, index=True)
    nombre       = Column(String(200), nullable=False)
    ruc          = Column(String(20))
    direccion    = Column(Text)
    telefono     = Column(String(20))
    email        = Column(String(100))
    fecha_creacion = Column(DateTime(timezone=True))
    activo       = Column(Boolean)

    seguros = relationship("SeguroBus", back_populates="compania")


class SeguroBus(Base):
    __tablename__ = "seguros_bus"
    __table_args__ = {"schema": SCHEMA}

    id_seguro           = Column(Integer, primary_key=True, index=True)
    id_bus              = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"))
    tipo_seguro         = Column(String(50))       # PASAJEROS / TERCEROS
    id_compania         = Column(Integer, ForeignKey(f"{SCHEMA}.companias_seguros.id_compania"))
    numero_poliza       = Column(String(100))
    fecha_inicio        = Column(Date, nullable=False)
    fecha_vencimiento   = Column(Date, nullable=False, index=True)
    monto_cobertura     = Column(Numeric)
    estado_seguro       = Column(String(20), default="VIGENTE")
    archivo_poliza_url  = Column(String(500))
    observaciones       = Column(Text)
    fecha_registro      = Column(DateTime, default=func.now())

    bus      = relationship("Bus", back_populates="seguros")
    compania = relationship("CompaniaSeguro", back_populates="seguros")


class DocumentoBus(Base):
    __tablename__ = "documentos_bus"
    __table_args__ = {"schema": SCHEMA}

    id_documento      = Column(Integer, primary_key=True, index=True)
    id_bus            = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"))
    tipo_documento    = Column(String(50))    # POD, RTD, HABILITACION, TITULO, etc.
    nombre_documento  = Column(String(200))
    fecha_emision     = Column(Date)
    fecha_vencimiento = Column(Date, index=True)
    estado_documento  = Column(String(20))    # VIGENTE, VENCIDO, POR_VENCER
    archivo_url       = Column(String(500))
    observaciones     = Column(Text)
    fecha_registro    = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="documentos")


class Alerta(Base):
    __tablename__ = "alertas"
    __table_args__ = {"schema": SCHEMA}

    id_alerta        = Column(Integer, primary_key=True, index=True)
    tipo_alerta      = Column(String(50))     # ITV, SEGURO_PASAJEROS, SEGURO_TERCEROS, DOCUMENTO
    id_bus           = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"))
    titulo           = Column(String(200))
    descripcion      = Column(Text)
    fecha_alerta     = Column(Date)
    prioridad        = Column(String(20))     # ALTA, MEDIA, BAJA
    estado_alerta    = Column(String(20), default="PENDIENTE")
    fecha_atencion   = Column(DateTime)
    usuario_atencion = Column(String(100))
    fecha_registro   = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="alertas")


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = {"schema": SCHEMA}

    id_auditoria    = Column(Integer, primary_key=True, index=True)
    tabla_afectada  = Column(String(100))
    id_registro     = Column(Integer)
    accion          = Column(String(20))   # INSERT, UPDATE, DELETE
    datos_anteriores = Column(JSONB)
    datos_nuevos    = Column(JSONB)
    usuario         = Column(String(100))
    fecha_accion    = Column(DateTime, default=func.now())
    ip_usuario      = Column(INET)


class Eot(Base):
    """
    Empresas Operadoras de Transporte — tabla READ-ONLY.
    Fuente: public.eots (sistema CID).
    El campo id_eot_vmt_hex es la FK que usa bus_empresa.id_eot.
    """
    __tablename__ = "eots"
    __table_args__ = {"schema": "public"}

    eot_id              = Column(Integer, primary_key=True, index=True)
    eot_nombre          = Column(String(70))
    eot_linea           = Column(String(30))
    cod_catalogo        = Column(Integer)
    cod_planilla        = Column(String(30))
    cod_epas            = Column(String(30))
    cod_tdp             = Column(String(30))
    situacion           = Column(Integer)
    gre_id              = Column(Integer)
    autorizado          = Column(Integer)
    operativo           = Column(Integer)
    reserva             = Column(Integer)
    permisionario       = Column(Boolean)
    operativo_declarado = Column(Integer)
    reserva_declarada   = Column(Integer)
    id_eot_vmt_hex      = Column(String, unique=True, index=True)   # FK usada en bus_empresa
    e_mail              = Column(String(70))
    eot_uf              = Column(Boolean)
    id_tipo_eot         = Column(Integer)
    agency_timezone     = Column(String)
    agency_url          = Column(String)
    agency_lang         = Column(String)


class Auxiliar(Base):
    """Tabla auxiliar de staging para importación desde Excel."""
    __tablename__ = "auxiliar"
    __table_args__ = {"schema": SCHEMA}

    orden                               = Column(Integer)
    hexadecimal                         = Column(String)
    marca                               = Column(String)
    año                                 = Column(Integer)
    chasis                              = Column(String)
    RUA                                 = Column(String, primary_key=True)
    pod_rtd                             = Column("POD / RTD", String)
    documentos                          = Column("Documentos", String)
    habilitacion                        = Column("Habilitacion", Date)
    seguro_pasajeros                    = Column("Seguro Pasajeros", Date)
    seguro_terceros                     = Column("Seguro Terceros", Date)
    tipo_de_servicio                    = Column("Tipo de Servicio", String)
    tipo_de_carroceria                  = Column("Tipo de Carroceria", String)
    marca_de_carroceria                 = Column("Marca de Carroceria", String)
    fecha_de_vencimiento_del_itv_anterior = Column("Fecha de Vencimiento del ITV Anterior", Date)
    fecha_de_itv                        = Column("Fecha de ITV", Date)
    vencimiento_de_itv                  = Column("Vencimiento de ITV", Date)
    situacion_de_itv_aprobada           = Column("Situacion de ITV Aprobada", String)
    codigo                              = Column("Codigo", Integer)
    empresa_linea                       = Column("Empresa_Linea", String)
    id_eot_vmt_hex                      = Column(String)
    id_marca                            = Column(Integer)
    id_marca_carroceria                 = Column(Integer)
    id_tipo_carroceria                  = Column(Integer)
