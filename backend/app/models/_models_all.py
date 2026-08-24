"""
Modelos ORM SQLAlchemy — mapeados al schema registro_habilitacion de PostgreSQL.
Tablas existentes: usuarios, buses, marcas, marcas_carroceria, tipos_carroceria,
bus_empresa, itv_bus, historial_itv, seguros_bus, companias_seguros,
documentos_bus, alertas, auditoria, auxiliar
"""

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean,
    Numeric, Text, ForeignKey, INET, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


SCHEMA = "registro_habilitacion"


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": SCHEMA}

    id_usuario      = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    email           = Column(String(100), unique=True, nullable=False)
    password_hash   = Column(String(255), nullable=False)
    nombre_completo = Column(String(200))
    rol             = Column(String(50))           # ADMIN, SUPERVISOR, OPERADOR, CONSULTA
    estado_usuario  = Column(String(20), default="ACTIVO")
    ultimo_acceso   = Column(DateTime)
    fecha_registro  = Column(DateTime, default=func.now())


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
    estado_bus          = Column(String(20), default="ACTIVO")
    tiene_rampa         = Column(Boolean, nullable=False, default=False, server_default="false")
    fecha_registro      = Column(DateTime, default=func.now())
    fecha_modificacion  = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relaciones
    marca           = relationship("Marca", back_populates="buses")
    tipo_carroceria = relationship("TipoCarroceria", back_populates="buses")
    marca_carroceria = relationship("MarcaCarroceria", back_populates="buses")
    asignaciones    = relationship("BusEmpresa", back_populates="bus")
    itv_registros   = relationship("ItvBus", back_populates="bus")
    seguros         = relationship("SeguroBus", back_populates="bus")
    documentos      = relationship("DocumentoBus", back_populates="bus")
    alertas         = relationship("Alerta", back_populates="bus")


class BusEmpresa(Base):
    """Asignación histórica bus ↔ EOT (N:N temporal vía id_eot_vmt_hex)."""
    __tablename__ = "bus_empresa"
    __table_args__ = {"schema": SCHEMA}

    id_asignacion        = Column(Integer, primary_key=True, index=True)
    id_bus               = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"), nullable=False)
    id_eot               = Column(String(255), nullable=False)
    fecha_asignacion     = Column(Date, nullable=False)
    fecha_fin_asignacion = Column(Date)
    estado_asignacion    = Column(String(20), default="ACTIVA")
    motivo               = Column(String(30))
    observaciones        = Column(Text)
    usuario_registro     = Column(String(100))
    fecha_registro       = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="asignaciones")


class ItvBus(Base):
    """Inspección Técnica Vehicular (historial unificado, con indicador de vigencia)."""
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
    es_vigente              = Column(Boolean, default=True, nullable=False, index=True)
    fecha_registro          = Column(DateTime, default=func.now())

    bus = relationship("Bus", back_populates="itv_registros")


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


class TipoSeguro(Base):
    __tablename__ = "tipos_seguro"
    __table_args__ = {"schema": SCHEMA}

    id_tipo_seguro = Column(Integer, primary_key=True, index=True)
    nombre         = Column(String(50), nullable=False, unique=True)
    descripcion    = Column(String(200))
    activo         = Column(Boolean, default=True)

    seguros = relationship("SeguroBus", back_populates="tipo")


class SeguroBus(Base):
    __tablename__ = "seguros_bus"
    __table_args__ = {"schema": SCHEMA}

    id_seguro           = Column(Integer, primary_key=True, index=True)
    id_bus              = Column(Integer, ForeignKey(f"{SCHEMA}.buses.id_bus"))
    id_tipo_seguro      = Column(Integer, ForeignKey(f"{SCHEMA}.tipos_seguro.id_tipo_seguro"), nullable=False)
    id_compania         = Column(Integer, ForeignKey(f"{SCHEMA}.companias_seguros.id_compania"))
    numero_poliza       = Column(String(100))
    fecha_inicio        = Column(Date, nullable=False)
    fecha_vencimiento   = Column(Date, nullable=False, index=True)
    monto_cobertura     = Column(Numeric)
    seguro_vigente      = Column(Boolean, default=True, nullable=False, index=True)
    archivo_poliza_url  = Column(String(500))
    observaciones       = Column(Text)
    fecha_registro      = Column(DateTime, default=func.now())

    bus      = relationship("Bus", back_populates="seguros")
    compania = relationship("CompaniaSeguro", back_populates="seguros")
    tipo     = relationship("TipoSeguro", back_populates="seguros")


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
