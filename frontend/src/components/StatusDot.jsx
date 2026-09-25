import { STATUS_DOT_COLORS } from '../utils/labels'
import { useLanguage } from '../context/LanguageContext'

/** Bolinha de status da tarefa — branca (contorno preto, "por iniciar"),
 * verde (no prazo), amarela (mistura, só em tarefas-pai) ou vermelha
 * (atrasada). A cor nunca é a única forma de comunicar o status: sempre
 * usada com `title` (tooltip) e, nas telas de detalhe, ao lado do rótulo
 * por extenso. */
export default function StatusDot({ color, size = 10 }) {
  const { labels } = useLanguage()
  const fill = STATUS_DOT_COLORS[color] || STATUS_DOT_COLORS.white
  const label = labels.STATUS_DOT_LABELS[color] || color
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className="inline-block shrink-0 rounded-full"
      style={{
        width: size,
        height: size,
        backgroundColor: fill,
        border: color === 'white' ? '1.5px solid #111' : '1.5px solid transparent',
      }}
    />
  )
}
