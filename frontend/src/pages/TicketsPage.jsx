import PageHeader from '../components/PageHeader'
import TicketsPanel from '../components/TicketsPanel'
import { useLanguage } from '../context/LanguageContext'

/** Tickets internos (pendentes): o consultor registra um incidente ligado a
 * uma tarefa de projeto, o gerente direciona e as interações ficam no
 * histórico até o solicitante confirmar a solução. */
export default function TicketsPage() {
  const { t } = useLanguage()
  return (
    <div>
      <PageHeader
        title={t('Tickets')}
        subtitle={t('Pendentes e incidentes internos por projeto e tarefa, com histórico de interações.')}
      />
      <TicketsPanel />
    </div>
  )
}
