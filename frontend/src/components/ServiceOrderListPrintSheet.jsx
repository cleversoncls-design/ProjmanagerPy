import { useLanguage } from '../context/LanguageContext'
import { formatDate, formatHoursDuration } from '../utils/format'

/** Impressão da LISTA de Ordens de Serviço (botão "Imprimir" do topo de
 * ServiceOrdersPage) — diferente do ServiceOrderPrintSheet (documento
 * oficial de UMA OS, botão "Imprimir" de cada linha): aqui é um relatório
 * interno com todas as OS do período filtrado, agrupadas por consultor,
 * com subtotal de horas por consultor e total geral ao final — pedido
 * explícito do usuário. Sem letterhead/assinatura (não é documento pro
 * cliente assinar); segue o idioma da interface (t()/labels), diferente do
 * ServiceOrderPrintSheet que é sempre em espanhol (modelo oficial fixo). */
export default function ServiceOrderListPrintSheet({ orders, filterSummary }) {
  const { t, labels } = useLanguage()

  const byResource = new Map()
  for (const order of orders) {
    if (!byResource.has(order.resource_name)) byResource.set(order.resource_name, [])
    byResource.get(order.resource_name).push(order)
  }
  const resourceNames = [...byResource.keys()].sort((a, b) => a.localeCompare(b))
  const grandTotal = orders.reduce((sum, order) => sum + Number(order.total_hours), 0)

  function statusLabel(order) {
    const allApproved = order.activities.every((a) => a.status === 'APPROVED')
    const anyUnscheduled = order.activities.some((a) => a.unscheduled)
    const base = allApproved ? labels.TIMESHEET_STATUS_LABELS.APPROVED : labels.TIMESHEET_STATUS_LABELS.PENDING
    return anyUnscheduled ? `${base} / ${t('Fora da agenda')}` : base
  }

  return (
    <div className="os-print-page mx-auto w-[210mm] bg-white px-[12mm] py-[10mm] text-black" style={{ fontFamily: 'Arial, Helvetica, sans-serif' }}>
      <h1 className="text-xl font-bold">{t('Ordens de Serviço')}</h1>
      {filterSummary.length > 0 && <p className="mt-1 text-[11px] text-black">{filterSummary.join(' · ')}</p>}

      {resourceNames.map((resourceName) => {
        const group = [...byResource.get(resourceName)].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
        const subtotal = group.reduce((sum, order) => sum + Number(order.total_hours), 0)
        return (
          <div key={resourceName} className="mt-4" style={{ breakInside: 'avoid' }}>
            <h2 className="border-b border-black pb-1 text-sm font-bold">{resourceName}</h2>
            <table className="mt-1 w-full border-collapse text-[11px]">
              <thead>
                <tr className="border-b border-black text-left">
                  <th className="py-1 pr-2">{t('Nº OS')}</th>
                  <th className="py-1 pr-2">{t('Data')}</th>
                  <th className="py-1 pr-2">{t('Cliente')}</th>
                  <th className="py-1 pr-2">{t('Projeto')}</th>
                  <th className="py-1 pr-2 text-right">{t('Total')}</th>
                  <th className="py-1 pr-2">{t('Status')}</th>
                </tr>
              </thead>
              <tbody>
                {group.map((order) => (
                  <tr key={`${order.date}-${order.project_id}-${order.resource_id}`} className="border-b border-black/30">
                    <td className="py-1 pr-2">{order.order_number}</td>
                    <td className="py-1 pr-2">{formatDate(order.date)}</td>
                    <td className="py-1 pr-2">{order.client_code} - {order.client_name}</td>
                    <td className="py-1 pr-2">{order.project_code} - {order.project_name}</td>
                    <td className="py-1 pr-2 text-right">{formatHoursDuration(order.total_hours)}</td>
                    <td className="py-1 pr-2">{statusLabel(order)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-right text-[11px] font-bold">
              {t('Subtotal')} — {resourceName}: {formatHoursDuration(subtotal)}
            </p>
          </div>
        )
      })}

      <p className="mt-4 border-t-2 border-black pt-2 text-right text-sm font-bold">
        {t('Total geral')}: {formatHoursDuration(grandTotal)}
      </p>
    </div>
  )
}
