// Dicionário de tradução da interface (pt-BR/es) — estilo "gettext": o
// texto em Português já escrito em cada tela É a própria chave de
// tradução (t('Salvar')), em vez de manter um catálogo de códigos em
// paralelo ao texto real. Nada em espanhol aqui é a "fonte da verdade" —
// pt-BR (o texto literal já escrito nas telas) é. Uma chave sem entrada
// em `es` simplesmente aparece em Português até alguém preencher.
//
// Plain data (sem React) de propósito: frontend/src/api/client.js (fora da
// árvore de componentes) também precisa traduzir uma mensagem antes de
// qualquer contexto React existir.

export const LANGUAGE_STORAGE_KEY = 'pmpy_language'
export const SUPPORTED_LANGUAGES = ['pt-BR', 'es']
export const DEFAULT_LANGUAGE = 'pt-BR'

export function getStoredLanguage() {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY)
    return SUPPORTED_LANGUAGES.includes(stored) ? stored : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

export function setStoredLanguage(lang) {
  try {
    if (SUPPORTED_LANGUAGES.includes(lang)) localStorage.setItem(LANGUAGE_STORAGE_KEY, lang)
  } catch {
    // localStorage bloqueado/cheio (modo privado etc.) — a preferência só
    // não sobrevive a um reload; quem estiver logado ainda recupera do
    // próprio cadastro (User.language) no próximo load.
  }
}

// Só as traduções ES precisam ficar aqui — pt-BR é o próprio texto que já
// está espalhado pelos componentes.
export const es = {
  // --- Navegação / chrome (Header, Sidebar) ---------------------------
  Dashboard: 'Panel',
  Projetos: 'Proyectos',
  Clientes: 'Clientes',
  'Usuários e recursos': 'Usuarios y recursos',
  Calendários: 'Calendarios',
  Workspace: 'Espacio de trabajo',
  Portfólio: 'Portafolio',
  Cadastros: 'Registros',
  'Visão geral': 'Visión general',
  'Detalhe do projeto': 'Detalle del proyecto',
  Sair: 'Salir',
  Notificações: 'Notificaciones',
  'Usar tema claro': 'Usar tema claro',
  'Usar tema escuro': 'Usar tema oscuro',
  'Usuário autenticado': 'Usuario autenticado',
  Idioma: 'Idioma',

  // --- Login -----------------------------------------------------------
  'Gestión de Proyectos': 'Gestión de Proyectos',
  'Entre com seu e-mail e senha para continuar.': 'Ingrese su correo electrónico y contraseña para continuar.',
  'E-mail': 'Correo electrónico',
  Senha: 'Contraseña',
  'Entrando…': 'Entrando…',
  Entrar: 'Entrar',
  'Não foi possível entrar.': 'No fue posible iniciar sesión.',

  // --- Ações/botões genéricos -------------------------------------------
  Salvar: 'Guardar',
  Cancelar: 'Cancelar',
  Editar: 'Editar',
  Excluir: 'Eliminar',
  Apagar: 'Eliminar',
  Fechar: 'Cerrar',
  Voltar: 'Volver',
  Aplicar: 'Aplicar',
  Confirmar: 'Confirmar',
  'Nova tarefa': 'Nueva tarea',
  'Salvando…': 'Guardando…',

  // --- Erro de conexão (api/client.js, fora da árvore React) ------------
  'Não foi possível conectar à API em {url}. Verifique se ela está rodando e se VITE_API_BASE_URL aponta para o lugar certo.':
    'No fue posible conectar con la API en {url}. Verifique que esté funcionando y que VITE_API_BASE_URL apunte al lugar correcto.',

  // --- Rótulos de perfil/status/tipo (utils/labels.js) -------------------
  // Perfis de usuário
  Administrador: 'Administrador',
  'Gerente de projetos': 'Gerente de proyectos',
  Consultor: 'Consultor',
  'PM do cliente': 'PM del cliente',
  'Usuário-chave': 'Usuario clave',
  // Status de projeto (Ativo é compartilhado com status de usuário)
  Ativo: 'Activo',
  Planejamento: 'Planificación',
  'Em espera': 'En espera',
  Concluído: 'Concluido',
  Cancelado: 'Cancelado',
  // Status de tarefa
  'Não iniciada': 'No iniciada',
  'Em andamento': 'En curso',
  Concluída: 'Concluida',
  Atrasada: 'Atrasada',
  // Tipo de tarefa
  Gestão: 'Gestión',
  Consultoria: 'Consultoría',
  Avulso: 'Eventual',
  // Status de validação do cliente
  'Não exigida': 'No exigida',
  'Aguardando cliente': 'Esperando cliente',
  Aprovada: 'Aprobada',
  Rejeitada: 'Rechazada',
  // Status de usuário
  Inativo: 'Inactivo',
  Bloqueado: 'Bloqueado',
  // Tipo de dependência entre tarefas
  'Término → Início': 'Fin → Inicio',
  'Início → Início': 'Inicio → Inicio',
  'Término → Término': 'Fin → Fin',
  'Início → Término': 'Inicio → Fin',
  TI: 'FI',
  II: 'II',
  TT: 'FF',
  IT: 'IF',
  // Dias da semana (abreviados)
  Seg: 'Lun',
  Ter: 'Mar',
  Qua: 'Mié',
  Qui: 'Jue',
  Sex: 'Vie',
  Sáb: 'Sáb',
  Dom: 'Dom',
  // Bolinha de status da tarefa
  'Por iniciar': 'Por iniciar',
  'No prazo': 'A tiempo',
  'Mistura de status': 'Mezcla de estados',
}

export function translate(lang, text, vars) {
  let result = lang === 'es' ? es[text] ?? text : text
  if (vars) {
    for (const [key, value] of Object.entries(vars)) {
      result = result.replaceAll(`{${key}}`, value)
    }
  }
  return result
}
