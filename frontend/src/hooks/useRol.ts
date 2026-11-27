import { useAuthStore } from '../stores/authStore'

/** Organismo EPS — Empresas Prestadoras de Servicio de Billetaje */
export const ORGANISMO_EPS = 4

/**
 * Devuelve el rol normalizado del usuario actual (ADMIN, SUPERVISOR, OPERADOR, CONSULTA).
 * Los usuarios con rol CONSULTA (viewer) solo pueden ver, no modificar.
 */
export function useRol() {
  const usuario = useAuthStore((s) => s.usuario)
  const rol = usuario?.rol ?? 'CONSULTA'
  const rolNorm = rol.trim().toUpperCase()
  const idOrganismo = usuario?.id_organismo ?? null

  /** true si el usuario puede crear/editar/eliminar */
  const puedeEditar = rolNorm !== 'CONSULTA'

  /** true si el usuario es admin */
  const esAdmin = rolNorm === 'ADMIN'

  /** true si el usuario es admin o supervisor */
  const esSupervisor = rolNorm === 'ADMIN' || rolNorm === 'SUPERVISOR'

  /** true si el usuario pertenece al organismo EPS (billettaje / SAM) */
  const esEps = idOrganismo === ORGANISMO_EPS

  return { rol: rolNorm, puedeEditar, esAdmin, esSupervisor, idOrganismo, esEps }
}
