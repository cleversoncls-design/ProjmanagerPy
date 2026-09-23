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
