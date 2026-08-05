import { Moon, Sun } from 'lucide-react'
import { useThemeStore } from '../stores/themeStore'

export default function ThemeToggle({ className = '' }: { className?: string }) {
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={toggleTheme}
      title={isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
      aria-label={isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
    >
      {isDark ? <Sun size={16} /> : <Moon size={16} />}
      <span className="theme-toggle-label">{isDark ? 'Claro' : 'Oscuro'}</span>
    </button>
  )
}
