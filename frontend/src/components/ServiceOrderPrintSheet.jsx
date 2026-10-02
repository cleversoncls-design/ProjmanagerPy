import { useLanguage } from '../context/LanguageContext'
import { formatDate, formatTime, formatHoursDuration, minutesToHM } from '../utils/format'

/** Uma folha impressa da Ordem de Serviço — modelo baseado no oficial TOTVS
 * que o usuário anexou (OS-000164169.pdf), depois ajustado por pedido dele
 * (endereço/razão social da empresa, campo "Tarea(s)" autônomo, rótulo
 * "Detalles" no lugar de "Tareas ejecutadas según planificación", Proyecto/
 * Total general promovidos pro cabeçalho da OS — ver histórico do arquivo).
 * Texto de documento (cabeçalho da empresa, rótulos "Fecha/Entrada/Salida/
 * Proyecto/Detalles...", aviso legal) é sempre em espanhol, e nunca passa
 * por t()/idioma da interface: é o texto fixo do documento oficial da
 * Resultar Servicios pro cliente assinar, não texto da UI do app. Só
 * rótulos que não vêm do modelo (nenhum aqui) usariam i18n.
 *
 * O destaque amarelo (.os-field, ver index.css) reproduz o mesmo destaque
 * que já existe no PDF original nos campos variáveis — não é anotação
 * nossa, é o próprio visual do documento que estamos reproduzindo.
 *
 * Uma OS pode ter mais de um apontamento (mesmo dia+projeto+consultor,
 * horários diferentes — "1 OS por dia + projeto + consultor", ver
 * `service_orders` em services.py). Proyecto é o mesmo pra todos os
 * apontamentos da OS (por definição do agrupamento), então aparece uma
 * única vez no cabeçalho, ao lado de Cliente — junto com "Total general"
 * quando há mais de um apontamento. Fecha também é a mesma pra todos os
 * apontamentos (mesmo critério de agrupamento) e por isso não se repete —
 * "Fecha Ref." no canto superior direito já cobre. Tipo Apunte (pedido do
 * usuário, "mais melhorias") subiu pro cabeçalho também: como o
 * agrupamento da OS não é por tipo, uma OS pode ter apontamentos de tipos
 * diferentes (Gestão/Consultoria/Avulso) — nesse caso os tipos distintos
 * aparecem juntos (ex.: "Gestión + Consultoría"), decisão confirmada com o
 * usuário. Só o bloco Entrada/Salida/Intervalo/Total/Tarea/Detalles
 * continua se repetindo, uma vez por apontamento, na mesma folha (Hoja
 * continua "1 / 1" — nunca quebramos em mais de uma página por OS). */
// Classificador Normal/Retrabalho + motivo(s) (pedido do usuário: imprimir
// na Ordem de Serviço, por tarefa) — rótulos fixos em espanhol, igual ao
// resto do documento oficial (nunca passam por t()/idioma da interface,
// ver nota acima); mesmos valores de WORK_CLASSIFICATION_LABELS/
// REWORK_REASON_LABELS (utils/labels.js) traduzidos pro espanhol.
const WORK_CLASSIFICATION_LABELS_ES = { NORMAL: 'Normal', REWORK: 'Retrabajo' }
const REWORK_REASON_LABELS_ES = {
  PRODUCT_ERROR: 'Error de Producto',
  INITIAL_CONFIG_ERROR: 'Error de Configuración inicial',
  DATA_LOAD_ERROR: 'Error de datos cargados',
  USER_DELAY_OR_ABSENCE: 'Retraso / Falta de Usuarios',
  ACCESS_ISSUE_SERVICE_SERVER: 'Problemas de Acceso (Servicios / Servidor)',
  ACCESS_ISSUE_NETWORK: 'Problemas de Acceso (Red)',
  CONSULTANT_CHANGE: 'Cambio de Consultor',
  POWER_OUTAGE: 'Falta de Energía Eléctrica',
}

export default function ServiceOrderPrintSheet({ order, tasksById }) {
  const { labels } = useLanguage()

  function tipoApunte(activity) {
    if (activity.task_id) {
      const task = tasksById[activity.task_id]
      return task ? labels.TASK_TYPE_LABELS[task.task_type] : '—'
    }
    return activity.is_transit ? labels.TASK_TYPE_LABELS.TRASLADO : labels.TASK_TYPE_LABELS.ADHOC
  }

  function tareaLabel(activity) {
    if (activity.wbs_code) return `${activity.wbs_code} - ${activity.task_name}`
    return activity.is_transit ? labels.TASK_TYPE_LABELS.TRASLADO : labels.TASK_TYPE_LABELS.ADHOC
  }

  // Tipo Apunte "geral" da OS, pro cabeçalho — junta os tipos distintos dos
  // apontamentos (ex.: "Gestión + Consultoría") quando a OS mistura mais de
  // um tipo; na maioria dos casos é só um tipo repetido.
  const tipoApunteGeral = [...new Set(order.activities.map(tipoApunte))].join(' + ')

  return (
    <div
      className="os-print-page mx-auto w-[210mm] bg-white px-[12mm] py-[10mm] text-black"
      style={{ fontFamily: 'Arial, Helvetica, sans-serif' }}
    >
      {/* Cabeçalho: marca + título + selo do canal */}
      <div className="flex items-center justify-between border-b-4 border-black pb-2">
        <div className="flex gap-0.5">
          <span className="h-8 w-1.5 -skew-x-12 bg-[#2a78d6]" />
          <span className="h-8 w-1.5 -skew-x-12 bg-[#1baf7a]" />
          <span className="h-8 w-1.5 -skew-x-12 bg-[#eda100]" />
        </div>
        <h1 className="text-2xl font-bold tracking-wide">ORDEN DE SERVICIO</h1>
        <div className="rounded border border-black px-2 py-1 text-center text-[9px] font-semibold leading-tight">
          CANAL
          <br />
          HOMOLOGADO
          <br />
          TOTVS
        </div>
      </div>

      {/* Empresa + numeração oficial */}
      <div className="mt-3 grid grid-cols-2 gap-4 border-b border-black pb-2 text-[11px]">
        <div>
          <p className="text-[10.25pt] font-bold">RESULTAR SERVICIOS Y SOLUCIONES E.A.S.</p>
          <p>Patricio Colman, Edificio Centenario - Piso 2 - Sala B</p>
          <p>CIUDAD DEL ESTE - ALTO PARANÁ</p>
          <p>PARAGUAI</p>
          <p>https://oeste.totvs.com/</p>
        </div>
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 self-start justify-self-end text-right">
          <span className="text-left">Nro. O.S.:</span>
          <span className="os-field font-bold">{order.order_number}</span>
          <span className="text-left">Hoja:</span>
          <span className="os-field font-bold">1 / 1</span>
          <span className="text-left">Fecha Ref.:</span>
          <span className="os-field font-bold">{formatDate(order.date)}</span>
          <span className="text-left">Emision:</span>
          <span className="os-field font-bold">{formatDate(order.emitted_at)}</span>
        </div>
      </div>

      {/* Consultor / Cliente / Proyecto — a OS inteira é sempre do mesmo
          projeto ("1 OS por dia + projeto + consultor", ver service_orders
          em services.py), então Proyecto aparece uma vez aqui, não repetido
          em cada bloco de apontamento; Total general acompanha junto,
          quando há mais de um apontamento na OS. */}
      <div className="mt-2 border-b border-black pb-2 text-[11px]">
        <p>
          Consultor: <span className="os-field font-bold">{order.resource_name}</span>
        </p>
        <div className="grid grid-cols-2 gap-x-4">
          <p>
            Cliente: <span className="os-field font-bold">{order.client_code} - {order.client_name}</span>
          </p>
          <p>
            Proyecto: <span className="os-field font-bold">{order.project_code} - {order.project_name}</span>
          </p>
        </div>
        <p className="mt-1">
          Tipo Apunte: <span className="os-field font-bold">{tipoApunteGeral}</span>
        </p>
        {order.activities.length > 1 && (
          <p className="mt-1 font-bold">
            Total general: <span className="os-field">{formatHoursDuration(order.total_hours)}</span>
          </p>
        )}
      </div>

      {/* Um bloco por apontamento */}
      {order.activities.map((activity, index) => (
        <div key={activity.id} className={`text-[11px] ${index === order.activities.length - 1 ? '' : 'border-b border-black'} py-2`}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            <p>
              Entrada: <span className="os-field font-bold">{formatTime(activity.start_time)}</span>
              {'  '}Salida: <span className="os-field font-bold">{formatTime(activity.end_time)}</span>
              {'  '}Intervalo: <span className="os-field font-bold">{minutesToHM(activity.break_minutes)}</span>
              {'  '}Total: <span className="os-field font-bold">{formatHoursDuration(activity.hours)}</span>
            </p>
            <p>
              Tarea(s): <span className="os-field font-bold">{tareaLabel(activity)}</span>
            </p>
          </div>

          {/* Classificador Normal/Retrabalho + motivo(s) (pedido do
              usuário) — só existe num apontamento de tarefa do projeto
              (work_classification nulo em Traslado/Avulso, ver
              Timesheet.work_classification). */}
          {activity.work_classification && (
            <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5">
              <p>
                Clasificación: <span className="os-field font-bold">{WORK_CLASSIFICATION_LABELS_ES[activity.work_classification] || activity.work_classification}</span>
              </p>
              {activity.work_classification === 'REWORK' && (
                <p>
                  Motivo del Retrabajo:{' '}
                  <span className="os-field font-bold">
                    {(activity.rework_reasons || []).map((reason) => REWORK_REASON_LABELS_ES[reason] || reason).join(', ') || '—'}
                  </span>
                </p>
              )}
            </div>
          )}

          <p className="mt-2">Detalles</p>
          <p className="os-field mt-1 inline-block">{activity.description || '—'}</p>
        </div>
      ))}

      <p className="mt-2 text-[9px] leading-snug text-black">
        Posibles restricciones acerca del contenido, apuntes u otros datos contenidos en la Orden de Servicio aqui
        representada deberán de ser apuntadas en reverso de este documento. El cliente tendrá el plazo adicional de
        48 horas, contados a partir de la emision de esta OS, para comentar posibles restricciones a través del
        canal de atención indicado en el encabezado de esta.
      </p>

      <div className="mt-16 grid grid-cols-2 gap-8 text-[10px]">
        <div>
          <p className="border-t border-black pt-1 font-bold">{order.resource_name}</p>
          <p>Responsable RESULTAR SERVICIOS Y SOLUCIONES E.A.S.</p>
        </div>
        <div>
          <p className="border-t border-black pt-1 font-bold">
            {order.client_code} - {order.client_name}
          </p>
          <p>Responsable Cliente</p>
        </div>
      </div>
    </div>
  )
}
