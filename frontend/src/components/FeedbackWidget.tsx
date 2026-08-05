import { useState, type FormEvent } from 'react'
import { mensajesApi } from '../api'
import { formatApiError } from '../api/client'

const TIPOS = [
  { value: 'sugerencia', label: 'Sugerencia' },
  { value: 'ajuste', label: 'Ajuste' },
  { value: 'soporte', label: 'Soporte' },
  { value: 'ampliacion', label: 'Ampliación' },
  { value: 'otro', label: 'Otro' },
] as const

export default function FeedbackWidget() {
  const [open, setOpen] = useState(false)
  const [tipo, setTipo] = useState<string>('soporte')
  const [mensaje, setMensaje] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  const resetForm = () => {
    setTipo('soporte')
    setMensaje('')
    setError(null)
  }

  const handleClose = () => {
    setOpen(false)
    setOk(false)
    setError(null)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!mensaje.trim() || sending) return
    setSending(true)
    setError(null)
    setOk(false)
    try {
      await mensajesApi.crear({ tipo, mensaje: mensaje.trim() })
      setOk(true)
      resetForm()
    } catch (err) {
      setError(formatApiError(err, 'No se pudo enviar el mensaje'))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="feedback-widget">
      {open && (
        <div className="feedback-panel" role="dialog" aria-label="Enviar feedback">
          <div className="feedback-panel-header">
            <div>
              <h3 className="feedback-panel-title">Comunicación</h3>
              <p className="feedback-panel-sub">
                Enviá sugerencias, ajustes o pedidos de soporte
              </p>
            </div>
            <button
              type="button"
              className="feedback-close"
              onClick={handleClose}
              aria-label="Cerrar"
            >
              ×
            </button>
          </div>

          {ok ? (
            <div className="feedback-success">
              <p>Mensaje enviado correctamente.</p>
              <p className="feedback-success-hint">Te responderemos a la brevedad.</p>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setOk(false)}>
                Enviar otro
              </button>
            </div>
          ) : (
            <form className="feedback-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="feedback-tipo">Tipo</label>
                <select
                  id="feedback-tipo"
                  className="form-control"
                  value={tipo}
                  onChange={(e) => setTipo(e.target.value)}
                  disabled={sending}
                >
                  {TIPOS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="feedback-mensaje">Mensaje</label>
                <textarea
                  id="feedback-mensaje"
                  className="form-control feedback-textarea"
                  rows={4}
                  maxLength={4000}
                  placeholder="Describí tu sugerencia, ajuste o consulta…"
                  value={mensaje}
                  onChange={(e) => setMensaje(e.target.value)}
                  disabled={sending}
                  required
                />
              </div>

              {error && <p className="form-error">{error}</p>}

              <button
                type="submit"
                className="btn btn-primary"
                disabled={sending || !mensaje.trim()}
                style={{ width: '100%' }}
              >
                {sending ? 'Enviando…' : 'Enviar mensaje'}
              </button>
            </form>
          )}
        </div>
      )}

      <button
        type="button"
        className={`feedback-fab${open ? ' is-open' : ''}`}
        onClick={() => {
          if (open) handleClose()
          else {
            setOpen(true)
            setOk(false)
          }
        }}
        aria-label={open ? 'Cerrar comunicación' : 'Abrir comunicación'}
        title="Comunicación"
      >
        {open ? '×' : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7A2.5 2.5 0 0 1 17.5 16H9l-4 3.5V6.5Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
            <path d="M8 9h8M8 12h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        )}
      </button>
    </div>
  )
}
