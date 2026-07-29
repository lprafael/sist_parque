import api from './client'

// ── Auth ──────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
  me: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
}

// ── Dashboard ─────────────────────────────────────
export const dashboardApi = {
  kpis: () => api.get('/dashboard/kpis'),
  vencimientosProximos: (dias = 30) =>
    api.get(`/dashboard/vencimientos-proximos?dias=${dias}`),
  distribucionEmpresas: () => api.get('/dashboard/distribucion-empresas'),
  distribucionAntiguedad: () => api.get('/dashboard/distribucion-antiguedad'),
  distribucionTipoServicio: () => api.get('/dashboard/distribucion-tipo-servicio'),
  distribucionMarcas: () => api.get('/dashboard/distribucion-marcas'),
}


// ── Buses ─────────────────────────────────────────
export const busesApi = {
  listar: (params?: Record<string, string | number>) =>
    api.get('/buses', { params }),
  obtener: (id: number) => api.get(`/buses/${id}`),
  crear: (data: unknown) => api.post('/buses', data),
  actualizar: (id: number, data: unknown) => api.put(`/buses/${id}`, data),
  eliminar: (id: number) => api.delete(`/buses/${id}`),
  marcas: () => api.get('/buses/catalogo/marcas'),
  tiposCarroceria: () => api.get('/buses/catalogo/tipos-carroceria'),
  marcasCarroceria: () => api.get('/buses/catalogo/marcas-carroceria'),
  tiposServicio: () => api.get('/buses/catalogo/tipos-servicio'),
}

// ── Empresas (EOT - read-only) ────────────────────
export const empresasApi = {
  listar: (params?: Record<string, string | number | boolean>) =>
    api.get('/empresas', { params }),
  obtener: (id_eot: string) => api.get(`/empresas/${id_eot}`),
  busesDeEmpresa: (
    id_eot: string,
    params?: { solo_activas?: boolean; a_fecha?: string },
  ) => api.get(`/empresas/${id_eot}/buses`, { params }),
  asignarBus: (data: unknown) => api.post('/empresas/asignaciones', data),
  bajaBus: (data: {
    id_bus: number
    fecha_fin: string
    motivo?: 'BAJA' | 'SUSPENSION'
    observaciones?: string
  }) => api.post('/empresas/asignaciones/baja', data),
  busesSinEmpresa: (params?: Record<string, string | number>) =>
    api.get('/empresas/asignaciones/sin-empresa', { params }),
  historialBus: (id_bus: number) =>
    api.get(`/empresas/asignaciones/bus/${id_bus}`),
  listarDocumentosEot: (id_eot: string, params?: { tipo_documento?: string }) =>
    api.get(`/empresas/${id_eot}/documentos`, { params }),
  crearDocumentoEot: (data: unknown) => api.post('/empresas/documentos', data),
  actualizarDocumentoEot: (id: number, data: unknown) =>
    api.put(`/empresas/documentos/${id}`, data),
  eliminarDocumentoEot: (id: number) => api.delete(`/empresas/documentos/${id}`),
}

// ── ITV ───────────────────────────────────────────
export const itvApi = {
  listar: (params?: Record<string, string | number>) =>
    api.get('/itv', { params }),
  obtener: (id: number) => api.get(`/itv/${id}`),
  registrar: (data: unknown) => api.post('/itv', data),
  actualizar: (id: number, data: unknown) => api.put(`/itv/${id}`, data),
  historialBus: (id_bus: number) => api.get(`/itv/historial/${id_bus}`),
}

// ── Seguros ───────────────────────────────────────
export const segurosApi = {
  listar: (params?: Record<string, string | number>) =>
    api.get('/seguros', { params }),
  crear: (data: unknown) => api.post('/seguros', data),
  actualizar: (id: number, data: unknown) => api.put(`/seguros/${id}`, data),
  companias: () => api.get('/seguros/companias'),
  tipos: () => api.get('/seguros/tipos'),
  crearCompania: (data: unknown) => api.post('/seguros/companias', data),
}

// ── Alertas ───────────────────────────────────────
export const alertasApi = {
  listar: (params?: Record<string, string | number>) =>
    api.get('/alertas', { params }),
  atender: (id: number, data: { usuario_atencion: string; observacion?: string }) =>
    api.put(`/alertas/${id}/atender`, data),
  ignorar: (id: number) => api.put(`/alertas/${id}/ignorar`, {}),
  limpiarTodas: () => api.delete('/alertas/limpiar-todas'),
}


// ── Documentos ────────────────────────────────────
export const documentosApi = {
  listarBus: (id_bus: number) => api.get(`/documentos/bus/${id_bus}`),
  crear: (data: unknown) => api.post('/documentos', data),
  eliminar: (id: number) => api.delete(`/documentos/${id}`),
}

// ── Usuarios ──────────────────────────────────────
export const usuariosApi = {
  listar: (params?: Record<string, string | number>) =>
    api.get('/usuarios', { params }),
  crear: (data: unknown) => api.post('/usuarios', data),
  actualizar: (id: number, data: unknown) => api.put(`/usuarios/${id}`, data),
}

// ── Auditoría ─────────────────────────────────────
export const auditoriaApi = {
  listar: (params?: Record<string, string | number>) =>
    api.get('/auditoria', { params }),
}

// ── Importador ────────────────────────────────────
export const importadorApi = {
  preview: (formData: FormData) =>
    api.post('/importador/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    }),
  aplicar: (formData: FormData) =>
    api.post('/importador/aplicar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    }),
  /** @deprecated usar preview */
  uploadExcel: (formData: FormData) =>
    api.post('/importador/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    }),
}

// ── Reportes ──────────────────────────────────────
export const reportesApi = {
  opciones: () => api.get('/reportes/opciones'),
  descargarBusesExcel: (params?: Record<string, string | number | boolean>) =>
    api.get('/reportes/buses/excel', { params, responseType: 'blob' }),
}

