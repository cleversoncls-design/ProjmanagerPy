import { useLanguage } from '../context/LanguageContext'
import { formatDate, formatTime, formatHoursDuration, minutesToHM } from '../utils/format'

/** Uma folha impressa da Ordem de Serviço, reproduzindo o modelo oficial
 * TOTVS que o usuário anexou (OS-000164169.pdf) — texto de documento
 * (cabeçalho da empresa, rótulos "Fecha/Entrada/Salida/Proyecto/Tareas
 * ejecutadas...", aviso legal) é sempre em espanhol, IGUAL ao modelo, e
 * nunca passa por t()/idioma da interface: é o texto fixo do documento
 * oficial da Resultar Servicios pro cliente assinar, não texto da UI do
 * app. Só rótulos que não vêm do modelo (nenhum aqui) usariam i18n.
 *
 * O destaque amarelo (.os-field, ver index.css) reproduz o mesmo destaque
 * que já existe no PDF original nos campos variáveis — não é anotação
 * nossa, é o próprio visual do documento que estamos reproduzindo.
 *
 * Uma OS pode ter mais de um apontamento (mesmo dia+projeto+consultor,
 * horários diferentes — "1 OS por dia + projeto + consultor", ver
 * `service_orders` em services.py) — o modelo original só mostra um
 * apontamento como exemplo; aqui o bloco Fecha/Entrada/Salida/Proyecto/
 * Horas-Tarefa/Tareas ejecutadas se repete uma vez por apontamento, na
 * mesma folha (Hoja continua "1 / 1" — nunca quebramos em mais de uma
 * página por OS), com um "Total general" ao final quando há mais de um. */
export default function ServiceOrderPrintSheet({ order, tasksById }) {
  const { labels } = useLanguage()

  function tipoApunte(activity) {
    if (activity.task_id) {
      const task = tasksById[activity.task_id]
      return task ? labels.TASK_TYPE_LABELS[task.task_type] : '—'
    }
    return labels.TASK_TYPE_LABELS.ADHOC
  }

  function tareaLabel(activity) {
    return activity.wbs_code ? `${activity.wbs_code} - ${activity.task_name}` : labels.TASK_TYPE_LABELS.ADHOC
  }

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
          <p className="font-bold">RESULTAR SERVICIOS Y SOLUCIONES S.R.L.</p>
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

      {/* Consultor / Cliente */}
      <div className="mt-2 border-b border-black pb-2 text-[11px]">
        <p>
          Consultor: <span className="os-field font-bold">{order.resource_name}</span>
        </p>
        <p>
          Cliente: <span className="os-field font-bold">{order.client_code} - {order.client_name}</span>
        </p>
      </div>

      {/* Um bloco por apontamento */}
      {order.activities.map((activity, index) => (
        <div key={activity.id} className={`text-[11px] ${index === order.activities.length - 1 ? '' : 'border-b border-black'} py-2`}>
          <div className="grid grid-cols-2">
            <p>
              Fecha: <span className="os-field font-bold">{formatDate(order.date)}</span>
            </p>
            <p>
              Tipo Apunte: <span className="os-field font-bold">{tipoApunte(activity)}</span>
            </p>
          </div>
          <p>
            Entrada: <span className="os-field font-bold">{formatTime(activity.start_time)}</span>
            {'  '}Salida: <span className="os-field font-bold">{formatTime(activity.end_time)}</span>
            {'  '}Intervalo: <span className="os-field font-bold">{minutesToHM(activity.break_minutes)}</span>
          </p>
          <p>
            Proyecto: <span className="os-field font-bold">{order.project_code} - {order.project_name}</span>
          </p>
          <p>
            Horas / Tarea(s):{' '}
            <span className="os-field font-bold">
              {formatHoursDuration(activity.hours)} / {tareaLabel(activity)}
            </span>
          </p>
          <p>
            Total: <span className="os-field font-bold">{formatHoursDuration(activity.hours)}</span>
          </p>

          <p className="mt-2">Tareas ejecutadas según planificación:</p>
          <p className="os-field mt-1 inline-block font-bold">{tareaLabel(activity)}</p>
          {activity.description && <p className="os-field mt-1 inline-block">{activity.description}</p>}
        </div>
      ))}

      {order.activities.length > 1 && (
        <p className="border-b border-black pb-2 text-[11px] font-bold">
          Total general: <span className="os-field">{formatHoursDuration(order.total_hours)}</span>
        </p>
      )}

      <p className="mt-2 text-[9px] leading-snug text-black">
        Posibles restricciones acerca del contenido, apuntes u otros datos contenidos en la Orden de Servicio aqui
        representada deberán de ser apuntadas en reverso de este documento. El cliente tendrá el plazo adicional de
        48 horas, contados a partir de la emision de esta OS, para comentar posibles restricciones a través del
        canal de atención indicado en el encabezado de esta.
      </p>

      <div className="mt-16 grid grid-cols-2 gap-8 text-[10px]">
        <div>
          <p className="border-t border-black pt-1 font-bold">{order.resource_name}</p>
          <p>Responsable RESULTAR SERVICIOS Y SOLUCIONES S.R.L.</p>
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
