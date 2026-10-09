import { useEffect, useMemo, useState } from 'react'
import * as clientsApi from '../api/clients'
import * as projectsApi from '../api/projects'
import Card from '../components/Card'
import { FormField, Select } from '../components/FormField'
import PageHeader from '../components/PageHeader'
import TicketIndicators from '../components/TicketIndicators'
import { useLanguage } from '../context/LanguageContext'

/** Dashboard Tickets (perfis de gestão): abertos por criticidade e status,
 * tempo de espera, horas gastas em tickets por projeto e carga por
 * responsável, com filtros por cliente e projeto. Endpoint:
 * GET /tickets-indicators (Gerente de Projetos vê só os projetos que conduz). */
export default function TicketsDashboardPage() {
  const { t } = useLanguage()
  const [clients, setClients] = useState([])
  const [projects, setProjects] = useState([])
  const [clientId, setClientId] = useState('')
  const [projectId, setProjectId] = useState('')

  useEffect(() => {
    clientsApi.listClients().then(setClients).catch(() => {})
    projectsApi.listProjects().then(setProjects).catch(() => {})
  }, [])

  const filteredProjects = useMemo(
    () => (clientId ? projects.filter((project) => project.client_id === clientId) : projects),
    [projects, clientId],
  )

  // Trocar o cliente limpa o projeto escolhido se ele não for desse cliente.
  function handleClientChange(event) {
    const next = event.target.value
    setClientId(next)
    if (projectId && next && projects.find((project) => project.id === projectId)?.client_id !== next) setProjectId('')
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('Dashboard Tickets')}
        subtitle={t('Indicadores dos tickets internos: criticidade, tempo de espera, horas gastas e carga por responsável.')}
      />
      <Card>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FormField label={t('Cliente')}>
            <Select value={clientId} onChange={handleClientChange}>
              <option value="">{t('Todos')}</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.legal_name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Projeto')}>
            <Select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">{t('Todos')}</option>
              {filteredProjects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.code} — {project.name}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
      </Card>
      <TicketIndicators projectId={projectId || null} clientId={clientId} />
    </div>
  )
}
