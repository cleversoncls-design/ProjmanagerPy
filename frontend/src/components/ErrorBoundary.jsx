import { Component } from 'react'

/** Barreira de erro (React error boundary) — sem isso, um erro de render
 * em QUALQUER componente (ex.: um modal específico como Estatísticas)
 * derruba a árvore React inteira e a tela fica em branco, sem nenhuma
 * pista do que aconteceu nem para o usuário nem para quem for depurar
 * depois. Com a barreira, o erro fica visível (mensagem + stack) em vez
 * de uma tela vazia, e dá para tentar de novo sem precisar recarregar a
 * página inteira (o que perderia o que a pessoa estava fazendo em outras
 * abas do navegador).
 *
 * Propositalmente não depende de nenhum contexto (idioma, tema etc.):
 * se o problema for justamente num desses provedores, a barreira ainda
 * precisa funcionar. Texto de fallback é bilíngue fixo por isso. */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] erro capturado:', error, info)
    this.setState({ info })
  }

  handleReset = () => {
    this.setState({ error: null, info: null })
  }

  render() {
    const { error, info } = this.state
    if (!error) return this.props.children

    const details = [error.stack || error.message || String(error), info?.componentStack ? `Component stack:${info.componentStack}` : '']
      .filter(Boolean)
      .join('\n\n')

    return (
      <div style={{ maxWidth: 720, margin: '40px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif', color: '#1f2937' }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Algo deu errado / Ha ocurrido un error</h1>
        <p style={{ marginBottom: 16, color: '#4b5563', fontSize: 14, lineHeight: 1.5 }}>
          Esta tela apresentou um erro inesperado e não pôde ser exibida. Tente novamente ou recarregue a página; se o
          problema continuar, copie os detalhes técnicos abaixo e envie ao suporte.
          <br />
          <br />
          Esta pantalla presentó un error inesperado y no pudo mostrarse. Intente de nuevo o recargue la página; si el
          problema persiste, copie los detalles técnicos de abajo y envíelos a soporte.
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <button
            type="button"
            onClick={this.handleReset}
            style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer', fontSize: 14 }}
          >
            Tentar novamente / Reintentar
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer', fontSize: 14 }}
          >
            Recarregar página / Recargar página
          </button>
        </div>
        <details
          open
          style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontSize: 12,
            fontFamily: 'ui-monospace, monospace',
            color: '#991b1b',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 6,
            padding: 12,
          }}
        >
          <summary style={{ cursor: 'pointer', fontWeight: 600, fontFamily: 'system-ui, sans-serif' }}>
            Detalhes técnicos / Detalles técnicos
          </summary>
          {details}
        </details>
      </div>
    )
  }
}
