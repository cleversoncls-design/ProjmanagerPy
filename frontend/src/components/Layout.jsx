import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

/** Casca da aplicação autenticada: faixa de destaque no topo + menu lateral
 * fixo + cabeçalho + conteúdo da rota — estrutura portada do app de
 * referência Resultar Servicios (components/desktop-route-shell.tsx). */
export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="h-1 shrink-0" style={{ backgroundColor: 'var(--nav-top-accent)' }} />
      <div className="flex min-h-0 flex-1 bg-[var(--page)]">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="min-w-0 flex-1 overflow-y-auto px-8 py-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
