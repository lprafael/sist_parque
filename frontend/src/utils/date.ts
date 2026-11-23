/** Zona horaria operativa del sistema (Paraguay). */
export const TZ_ASUNCION = 'America/Asuncion'

const DATE_OPTS: Intl.DateTimeFormatOptions = {
  timeZone: TZ_ASUNCION,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
}

const DATETIME_OPTS: Intl.DateTimeFormatOptions = {
  ...DATE_OPTS,
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
}

function asDate(value: string | number | Date | null | undefined): Date | null {
  if (value == null || value === '') return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Fecha calendario en America/Asuncion (es-PY). */
export function formatDateAsuncion(value: string | number | Date | null | undefined): string {
  const d = asDate(value)
  return d ? d.toLocaleDateString('es-PY', DATE_OPTS) : '—'
}

/** Fecha y hora en America/Asuncion (es-PY). */
export function formatDateTimeAsuncion(value: string | number | Date | null | undefined): string {
  const d = asDate(value)
  return d ? d.toLocaleString('es-PY', DATETIME_OPTS) : '—'
}
