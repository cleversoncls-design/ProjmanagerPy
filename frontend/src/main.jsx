import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {/* Barreira externa: cobre erros que aconteçam nos próprios provedores
        (Theme/Auth/Language), fora do alcance da barreira interna do App.jsx. */}
    <ErrorBoundary>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </ErrorBoundary>
  </StrictMode>,
)
