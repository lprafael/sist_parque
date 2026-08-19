import { useAuthStore } from '../stores/authStore'

/**
 * Devuelve el rol normalizado del usuario actual (ADMIN, SUPERVISOR, OPERADOR, CONSULTA).
 * Los usuarios con rol CONSULTA (viewer) solo pueden ver, no modificar.
 */
export function useRol() {
  const rol = useAuthStore((s) => s.usuario?.rol ?? 'CONSULTA')
  const rolNorm = rol.trim().toUpperCase()

  /** true si el usuario puede crear/editar/eliminar */
  const puedeEditar = rolNorm !== 'CONSULTA'

  /** true si el usuario es admin */
  const esAdmin = rolNorm === 'ADMIN'

  /** true si el usuario es admin o supervisor */
  const esSupervisor = rolNorm === 'ADMIN' || rolNorm === 'SUPERVISOR'

  return { rol: rolNorm, puedeEditar, esAdmin, esSupervisor }
}
