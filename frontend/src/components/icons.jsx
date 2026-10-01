/** Ícones em SVG inline, minimalistas (traço único), para não depender de
 * uma biblioteca de ícones externa — decisão de escopo do Fase 3 (Tailwind
 * + componentes próprios, sem lib de componentes/ícones de terceiros). */
function Icon({ children, size = 18, ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  )
}

export const HomeIcon = (props) => (
  <Icon {...props}>
    <path d="M3 11.5 12 4l9 7.5" />
    <path d="M5.5 10v9a1 1 0 0 0 1 1H17.5a1 1 0 0 0 1-1v-9" />
  </Icon>
)

export const BriefcaseIcon = (props) => (
  <Icon {...props}>
    <rect x="3" y="7.5" width="18" height="12" rx="2" />
    <path d="M8 7.5V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1.5" />
    <path d="M3 12.5h18" />
  </Icon>
)

export const BuildingIcon = (props) => (
  <Icon {...props}>
    <rect x="4" y="3" width="16" height="18" rx="1.2" />
    <path d="M8 7h1.5M14.5 7H16M8 11h1.5M14.5 11H16M8 15h1.5M14.5 15H16" />
  </Icon>
)

export const UsersIcon = (props) => (
  <Icon {...props}>
    <circle cx="9" cy="8.5" r="3" />
    <path d="M2.5 20c0-3.3 2.9-6 6.5-6s6.5 2.7 6.5 6" />
    <path d="M15.5 4.6c1.5.5 2.6 1.9 2.6 3.6 0 1.7-1.1 3.1-2.6 3.6" />
    <path d="M17 14.3c2.3.7 4 2.8 4 5.7" />
  </Icon>
)

export const CalendarIcon = (props) => (
  <Icon {...props}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
    <path d="M3.5 9.5h17M8 3v3.5M16 3v3.5" />
  </Icon>
)

export const ChevronRightIcon = (props) => (
  <Icon {...props}>
    <path d="M9 5.5 15.5 12 9 18.5" />
  </Icon>
)

export const ChevronLeftIcon = (props) => (
  <Icon {...props}>
    <path d="M15 5.5 8.5 12l6.5 6.5" />
  </Icon>
)

// Seta do seletor de cor do projeto (ColorListPicker) — mesmo estilo dos
// outros chevrons acima.
export const ChevronDownIcon = (props) => (
  <Icon {...props}>
    <path d="M5.5 9 12 15.5 18.5 9" />
  </Icon>
)

// Agenda de consultores (SchedulesPage) — bloco de horário agendado.
export const ClockIcon = (props) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Icon>
)

// Aprovar/rejeitar apontamento (TimesheetsPage).
export const CheckIcon = (props) => (
  <Icon {...props}>
    <path d="M4.5 12.5 9.5 17.5 19.5 6.5" />
  </Icon>
)

export const XIcon = (props) => (
  <Icon {...props}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
)

// Apontamento de horas (TimesheetsPage) — prancheta com check.
export const ClipboardCheckIcon = (props) => (
  <Icon {...props}>
    <rect x="5" y="4.5" width="14" height="17" rx="1.8" />
    <path d="M9 4.5V3.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1" />
    <path d="M8.5 13l2.2 2.2L15.5 10.5" />
  </Icon>
)

// Aprovações de horas (TimesheetApprovalsPage) — selo/crachá com check,
// distinto da prancheta do Apontamento de horas (ClipboardCheckIcon).
export const BadgeCheckIcon = (props) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M8.5 12.3 10.8 14.6 15.5 9.7" />
  </Icon>
)

// Ordens de Serviço (ServiceOrdersPage) — documento com linhas.
export const FileTextIcon = (props) => (
  <Icon {...props}>
    <path d="M7 3.5h7l3.5 3.5V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
    <path d="M14 3.5V7h3.5" />
    <path d="M8.5 12h7M8.5 15.5h7M8.5 8.5h3" />
  </Icon>
)

export const PanelLeftIcon = (props) => (
  <Icon {...props}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="M9.5 4.5v15" />
  </Icon>
)

export const SunIcon = (props) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2.3M12 19.2v2.3M4.4 4.4l1.6 1.6M18 18l1.6 1.6M2.5 12h2.3M19.2 12h2.3M4.4 19.6 6 18M18 6l1.6-1.6" />
  </Icon>
)

export const MoonIcon = (props) => (
  <Icon {...props}>
    <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
  </Icon>
)

export const BellIcon = (props) => (
  <Icon {...props}>
    <path d="M6 9.5a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 13.5 6 9.5Z" />
    <path d="M10 18.5a2 2 0 0 0 4 0" />
  </Icon>
)

export const LogoutIcon = (props) => (
  <Icon {...props}>
    <path d="M9 20H5.5a1.5 1.5 0 0 1-1.5-1.5v-13A1.5 1.5 0 0 1 5.5 4H9" />
    <path d="M15.5 16.5 20 12l-4.5-4.5" />
    <path d="M20 12H9" />
  </Icon>
)

// Barra de ações da grade de Tarefas (ver TasksTab em ProjectDetailPage) e
// ações por linha — ícones adicionados pra substituir botões de texto
// numa barra que já tinha 5+ ações, sem perder o significado (cada um
// carrega um `title` pro navegador mostrar como dica ao passar o mouse).
export const DownloadIcon = (props) => (
  <Icon {...props}>
    <path d="M12 3v12.5" />
    <path d="M7 11l5 5 5-5" />
    <path d="M4.5 19.5h15" />
  </Icon>
)

export const FlagIcon = (props) => (
  <Icon {...props}>
    <path d="M6 3.5v17" />
    <path d="M6 4.5c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0V13c-1.5 1.2-3 1.2-4.5 0s-3-1.2-4.5 0Z" />
  </Icon>
)

export const HashIcon = (props) => (
  <Icon {...props}>
    <path d="M9.5 3.5 7 20.5M17 3.5l-2.5 17" />
    <path d="M4 8.5h16.5M3.5 15.5H20" />
  </Icon>
)

export const RefreshIcon = (props) => (
  <Icon {...props}>
    <path d="M20 11a8 8 0 0 0-14.5-4.5L3 9" />
    <path d="M3 4v5h5" />
    <path d="M4 13a8 8 0 0 0 14.5 4.5L21 15" />
    <path d="M21 20v-5h-5" />
  </Icon>
)

export const PlusIcon = (props) => (
  <Icon {...props}>
    <path d="M12 4.5v15M4.5 12h15" />
  </Icon>
)

export const PencilIcon = (props) => (
  <Icon {...props}>
    <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3Z" />
    <path d="M13.5 8 16 10.5" />
  </Icon>
)

export const MoveIcon = (props) => (
  <Icon {...props}>
    <path d="M12 3v18M3 12h18" />
    <path d="M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3" />
  </Icon>
)

export const TrashIcon = (props) => (
  <Icon {...props}>
    <path d="M5 7.5h14" />
    <path d="M9.5 7.5V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2.5" />
    <path d="M7 7.5 7.8 19a1.5 1.5 0 0 0 1.5 1.4h5.4a1.5 1.5 0 0 0 1.5-1.4l.8-11.5" />
    <path d="M10.3 11v6M13.7 11v6" />
  </Icon>
)

export const ColumnsIcon = (props) => (
  <Icon {...props}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="1.5" />
    <path d="M9.5 4.5v15M14.5 4.5v15" />
  </Icon>
)

// Ação "Redefinir senha" por linha (tela de Usuários) — substitui o botão
// de texto, mesmo padrão de ícone+title/aria-label do IconButton.
export const KeyIcon = (props) => (
  <Icon {...props}>
    <circle cx="8" cy="15" r="4" />
    <path d="M11 12 19.5 3.5" />
    <path d="M16.5 6.5 19 9M14 9l2 2" />
  </Icon>
)

// Seletor de idioma da tela de Login (splash sempre escuro, fora do tema
// claro/escuro do conteúdo — ver LoginPage.jsx).
// "Detalhes" (expandir/ver itens de uma linha-resumo) — ServiceOrdersPage.
export const EyeIcon = (props) => (
  <Icon {...props}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="2.6" />
  </Icon>
)

// "Imprimir" por linha (ServiceOrdersPage) — mesmo estilo de traço único
// dos outros ícones de ação.
export const PrinterIcon = (props) => (
  <Icon {...props}>
    <path d="M7 8.5V4h10v4.5" />
    <rect x="4" y="8.5" width="16" height="8" rx="1.5" />
    <path d="M7 14.5h10V20H7v-5.5Z" />
  </Icon>
)

export const GlobeIcon = (props) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18" />
    <path d="M12 3c2.8 2.5 4.3 5.7 4.3 9s-1.5 6.5-4.3 9c-2.8-2.5-4.3-5.7-4.3-9s1.5-6.5 4.3-9Z" />
  </Icon>
)

// "Copiar estrutura de outro projeto" (aba Tarefas, projeto vazio) — duas
// folhas sobrepostas, ícone padrão de "duplicar/copiar".
export const CopyIcon = (props) => (
  <Icon {...props}>
    <rect x="8.5" y="8.5" width="11" height="11" rx="1.5" />
    <path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8a1.5 1.5 0 0 0 1.5 1.5h2.5" />
  </Icon>
)
