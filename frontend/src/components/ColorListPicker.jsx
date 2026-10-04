import { useEffect, useMemo, useRef, useState } from 'react'
import { useLanguage } from '../context/LanguageContext'
import { PROJECT_COLOR_PALETTE, PROJECT_STRIPED_PATTERN, colorNameFor } from '../utils/colorPalette'
import { ChevronDownIcon } from './icons'

/** Seletor de cor do projeto — campo tipo lista (like a combobox), com as
 * 256 cores nomeadas de PROJECT_COLOR_PALETTE (ver utils/colorPalette.js),
 * no lugar da paleta categórica fixa de 8 cores que existia antes
 * (ColorSwatchPicker, removido). Com 256 opções, uma grade de bolinhas
 * vira ilegível — por isso lista rolável + busca por nome/hex, igual um
 * <select> de verdade só que com a amostra de cor ao lado de cada nome.
 *
 * `usedColors` (opcional): Map<hexMaiúsculo, rótulo> das cores já em uso
 * por outros projetos ativos (ver _ensure_color_available no backend) —
 * cada uma vira uma opção desabilitada na lista, com o nome do projeto
 * dono no tooltip. `disabled` (opcional): trava o seletor inteiro (ex.:
 * projeto finalizado, cor não pode mais ser trocada enquanto estiver
 * assim). `striped` (opcional): mostra o padrão listrado na amostra
 * fechada no lugar do hex — usado junto com `disabled` pra um projeto já
 * finalizado (ver Project.color_striped). */
export default function ColorListPicker({ value, onChange, usedColors, disabled, striped }) {
  const { t } = useLanguage()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const containerRef = useRef(null)
  const searchRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    function handlePointerDown(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    // Foca a busca ao abrir, pra já poder digitar direto.
    searchRef.current?.focus()
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return PROJECT_COLOR_PALETTE
    return PROJECT_COLOR_PALETTE.filter(
      (entry) => t(entry.name).toLowerCase().includes(needle) || entry.hex.toLowerCase().includes(needle),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  const currentLabel = value ? t(colorNameFor(value)) : t('Selecione uma cor')

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((prev) => !prev)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex w-full items-center gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left text-sm text-[var(--text-primary)] focus:border-[var(--series-1)] focus:outline-none focus:ring-1 focus:ring-[var(--series-1)] ${
          disabled ? 'cursor-not-allowed opacity-60' : ''
        }`}
      >
        <span
          className="h-5 w-5 shrink-0 rounded-full border border-[var(--border)]"
          style={striped ? PROJECT_STRIPED_PATTERN : { backgroundColor: value || 'transparent' }}
        />
        <span className="flex-1 truncate">{striped ? t('Listrado (projeto finalizado)') : currentLabel}</span>
        {!disabled && <ChevronDownIcon size={16} className="shrink-0 text-[var(--text-muted)]" />}
      </button>

      {open && !disabled && (
        <div
          role="listbox"
          className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg"
        >
          <div className="border-b border-[var(--border)] p-2">
            <input
              ref={searchRef}
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('Buscar cor por nome...')}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--page)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
            />
          </div>
          <div className="max-h-64 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="px-2.5 py-2 text-xs text-[var(--text-muted)]">{t('Nenhuma cor encontrada.')}</p>
            ) : (
              filtered.map((entry) => {
                const selected = value?.toUpperCase() === entry.hex
                // A própria cor atual do projeto nunca fica desabilitada
                // (senão o formulário travaria sem opção de "não mudar").
                const usedByLabel = !selected ? usedColors?.get(entry.hex) : undefined
                const isUsed = Boolean(usedByLabel)
                return (
                  <button
                    key={entry.id}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    aria-disabled={isUsed}
                    disabled={isUsed}
                    title={isUsed ? t('Já em uso por {project}', { project: usedByLabel }) : undefined}
                    onClick={() => {
                      if (isUsed) return
                      onChange(entry.hex)
                      setOpen(false)
                      setQuery('')
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors ${
                      isUsed
                        ? 'cursor-not-allowed opacity-40'
                        : 'hover:bg-[var(--page)]'
                    } ${selected ? 'bg-[var(--page)] font-semibold text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}`}
                  >
                    <span
                      className="h-5 w-5 shrink-0 rounded-full border border-[var(--border)]"
                      style={{ backgroundColor: entry.hex }}
                    />
                    <span className="truncate">{t(entry.name)}</span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
