import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { authApi } from '../api'
import { Lock, User, Bus } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await authApi.login(username, password)
      login(data.access_token, data.refresh_token, data.usuario)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-base)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 20, right: 20, zIndex: 2 }}>
        <ThemeToggle />
      </div>

      {/* Background glow */}
      <div style={{
        position: 'absolute',
        width: '600px', height: '600px',
        background: 'radial-gradient(circle, rgba(63,81,181,0.15) 0%, transparent 70%)',
        top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
      }} />

      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '24px',
        padding: '48px 44px',
        width: '100%',
        maxWidth: '420px',
        position: 'relative',
        boxShadow: 'var(--shadow-lg)',
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <div style={{
            width: '64px', height: '64px',
            background: 'linear-gradient(135deg, var(--brand-500), var(--brand-800))',
            borderRadius: '18px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 8px 24px rgba(63,81,181,0.4)',
          }}>
            <Bus size={30} color="white" />
          </div>
          <div style={{
            display: 'inline-block',
            background: 'linear-gradient(135deg, var(--brand-500), var(--accent-500))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            fontFamily: 'Outfit, sans-serif',
            fontSize: '1.5rem',
            fontWeight: '800',
            marginBottom: '6px',
          }}>
            Parque Automotor
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            Viceministerio de Transporte — Paraguay
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Usuario</label>
            <div style={{ position: 'relative' }}>
              <User size={16} style={{
                position: 'absolute', left: '12px', top: '50%',
                transform: 'translateY(-50%)', color: 'var(--text-muted)',
              }} />
              <input
                id="login-username"
                className="form-control"
                style={{ paddingLeft: '38px' }}
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Nombre de usuario"
                autoFocus
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Contraseña</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{
                position: 'absolute', left: '12px', top: '50%',
                transform: 'translateY(-50%)', color: 'var(--text-muted)',
              }} />
              <input
                id="login-password"
                type="password"
                className="form-control"
                style={{ paddingLeft: '38px' }}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Contraseña"
                required
              />
            </div>
          </div>

          {error && (
            <div style={{
              background: 'rgba(244,67,54,0.12)',
              border: '1px solid rgba(244,67,54,0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 14px',
              color: '#ff8a80',
              fontSize: '0.82rem',
              marginBottom: '16px',
            }}>
              {error}
            </div>
          )}

          <button
            id="login-submit"
            type="submit"
            className="btn btn-primary btn-lg"
            style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }}
            disabled={loading}
          >
            {loading ? 'Iniciando sesión...' : 'Ingresar al sistema'}
          </button>
        </form>

        <p style={{
          textAlign: 'center',
          marginTop: '24px',
          fontSize: '0.72rem',
          color: 'var(--text-muted)',
        }}>
          Depto. de Registro y Habilitación · VMT
        </p>
      </div>
    </div>
  )
}
