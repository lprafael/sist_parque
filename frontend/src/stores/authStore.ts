import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface Usuario {
  id_usuario: number
  username: string
  email: string
  nombre_completo?: string
  rol: string
  estado_usuario: string
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  usuario: Usuario | null
  isAuthenticated: boolean
  setTokens: (access: string, refresh: string) => void
  setUsuario: (u: Usuario) => void
  login: (access: string, refresh: string, usuario: Usuario) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      usuario: null,
      isAuthenticated: false,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),

      setUsuario: (u) =>
        set({ usuario: u, isAuthenticated: true }),

      login: (access, refresh, usuario) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          usuario,
          isAuthenticated: true,
        }),

      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          usuario: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: 'parque-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        usuario: state.usuario,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
