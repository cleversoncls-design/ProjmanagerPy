import { PROJECT_COLOR_KEYS } from '../utils/labels'

/** Seletor de cor do projeto — uma "palheta de cores" (como pedido), mas
 * restrita às 8 cores categóricas já validadas do sistema (--series-1..8,
 * ver index.css e a skill de dataviz: nunca inventar cor nova fora de uma
 * paleta com separação testada pra daltonismo). Usado no cadastro/edição de
 * projeto; a Agenda de consultores só LÊ `project.color`, nunca escolhe. */
export default function ColorSwatchPicker({ value, onChange, colorLabels = {} }) {
  return (
    <div className="flex flex-wrap gap-2">
      {PROJECT_COLOR_KEYS.map((key) => {
        const selected = value === key
        return (
          <button
            key={key}
            type="button"
            title={colorLabels[key] || key}
            aria-label={colorLabels[key] || key}
            aria-pressed={selected}
            onClick={() => onChange(key)}
            className={`h-7 w-7 shrink-0 rounded-full transition-[box-shadow,transform] ${
              selected ? 'scale-110 ring-2 ring-offset-2 ring-offset-[var(--surface)]' : 'hover:scale-105'
            }`}
            style={{ backgroundColor: `var(--${key})`, ...(selected ? { '--tw-ring-color': `var(--${key})` } : {}) }}
          />
        )
      })}
    </div>
  )
}
