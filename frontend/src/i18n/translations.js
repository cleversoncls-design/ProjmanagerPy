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
  // --- Página Projetos / Clientes / Usuários / Calendários / Detalhe do projeto (varredura de tradução) ---
  '% Realizado': '% Completado',
  '% concluído': '% completado',
  '% concluído (Duração)': '% completado (Duración)',
  '% concluído (Trabalho)': '% completado (Trabajo)',
  '% previsto': '% previsto',
  '% realizado': '% completado',
  '2 letras': '2 letras',
  'Adicionar': 'Agregar',
  'Apagando…': 'Eliminando…',
  'Apagar tarefa': 'Eliminar tarea',
  'Aprovação do cliente': 'Aprobación del cliente',
  'Atraso (dias)': 'Retraso (días)',
  'Atual': 'Actual',
  'Atualizando data de status…': 'Actualizando fecha de estado…',
  'Bloqueado impede login imediatamente.': 'Bloqueado impide el inicio de sesión de inmediato.',
  'Cadastro de clientes atendidos pela consultoria.': 'Registro de clientes atendidos por la consultoría.',
  'Calendário do projeto': 'Calendario del proyecto',
  'Calendário pessoal': 'Calendario personal',
  'Calendários cadastrados': 'Calendarios registrados',
  'Capacidade diária (h)': 'Capacidad diaria (h)',
  'Cidade': 'Ciudad',
  'Cidade/UF': 'Ciudad/Estado',
  'Cliente': 'Cliente',
  'Colocar antes de': 'Colocar antes de',
  'Colunas': 'Columnas',
  'Colunas da grade de tarefas': 'Columnas de la grilla de tareas',
  'Contato': 'Contacto',
  'Custo': 'Costo',
  'Custo interno (US$/h)': 'Costo interno (US$/h)',
  'Custo real': 'Costo real',
  'Código': 'Código',
  'Código WBS': 'Código WBS',
  'Data': 'Fecha',
  'Data de status': 'Fecha de estado',
  'Data de status:': 'Fecha de estado:',
  'Data-base para % previsto e status das tarefas.': 'Fecha base para % previsto y estado de las tareas.',
  'Deixe em branco para colocar por último entre as irmãs.': 'Déjelo en blanco para colocar al final entre las hermanas.',
  'Deixe em branco para mover para a raiz do projeto.': 'Déjelo en blanco para mover a la raíz del proyecto.',
  'Deixe em branco para uma tarefa de topo (raiz).': 'Déjelo en blanco para una tarea de nivel superior (raíz).',
  'Depois de mover, use "Recalcular WBS/EAP" para renumerar e "Recalcular tudo" se a tarefa tiver predecessoras.': 'Después de mover, use "Recalcular WBS/EAP" para renumerar y "Recalcular todo" si la tarea tiene predecesoras.',
  'Descrição': 'Descripción',
  'Desempenho do cronograma (Earned Value, em horas)': 'Desempeño del cronograma (Valor Ganado, en horas)',
  'Dias úteis': 'Días hábiles',
  'Dias úteis e feriados usados no cálculo de cronograma e capacidade.': 'Días hábiles y feriados usados en el cálculo de cronograma y capacidad.',
  'Duração': 'Duración',
  'Duração (dias)': 'Duración (días)',
  'E-mail do contato': 'Correo electrónico del contacto',
  'Editar feriado': 'Editar feriado',
  'Editar projeto': 'Editar proyecto',
  'Editar recalcula a Duração.': 'Editar recalcula la Duración.',
  'Editar recalcula o Trabalho.': 'Editar recalcula el Trabajo.',
  'Editar recurso': 'Editar recurso',
  'Editar tarefa': 'Editar tarea',
  'Editar usuário': 'Editar usuario',
  'Escolha quais colunas aparecem e em que ordem — WBS, nome da tarefa e as ações da linha ficam sempre fixas nas pontas.': 'Elija qué columnas aparecen y en qué orden — WBS, nombre de la tarea y las acciones de la fila quedan siempre fijas en los extremos.',
  'Essa ação não pode ser desfeita.': 'Esta acción no se puede deshacer.',
  'Estatísticas': 'Estadísticas',
  'Estatísticas do projeto': 'Estadísticas del proyecto',
  'Ex.: "1.2"': 'Ej.: "1.2"',
  'Ex.: "Baseline inicial", "Revisão de escopo #2".': 'Ej.: "Línea base inicial", "Revisión de alcance #2".',
  'Ex.: "Consultor sênior", "Gerente de projetos".': 'Ej.: "Consultor sénior", "Gerente de proyectos".',
  'Ex.: 16': 'Ej.: 16',
  'Ex.: 2': 'Ej.: 2',
  'Ex.: Baseline inicial': 'Ej.: Línea base inicial',
  'Ex.: Baseline inicial, Revisão de escopo #2.': 'Ej.: Línea base inicial, Revisión de alcance #2.',
  'Excluindo…': 'Eliminando…',
  'Excluir feriado': 'Eliminar feriado',
  'Exportar (Excel)': 'Exportar (Excel)',
  'Exportar PNG': 'Exportar PNG',
  'Feriados': 'Feriados',
  'Fim': 'Fin',
  'Fim do período exibido': 'Fin del período mostrado',
  'Fim na linha base:': 'Fin en la línea base:',
  'Fim planejado': 'Fin planificado',
  'Financeiro': 'Financiero',
  'Função': 'Función',
  'Gerando planilha…': 'Generando planilla…',
  'Gerente responsável': 'Gerente responsable',
  'Grava a Duração, o Trabalho e as datas planejadas de hoje de todas as tarefas como a nova linha de base do projeto — usada para comparar com o realizado depois (colunas "Linha base" na grade e variância de término nas Estatísticas).': 'Registra la Duración, el Trabajo y las fechas planificadas de hoy de todas las tareas como la nueva línea base del proyecto — usada para comparar con lo real después (columnas "Línea base" en la grilla y variación de término en Estadísticas).',
  'Horas': 'Horas',
  'Horas alocadas': 'Horas asignadas',
  'Horas de consultoria': 'Horas de consultoría',
  'Horas de gestão': 'Horas de gestión',
  'Início': 'Inicio',
  'Início do período exibido': 'Inicio del período mostrado',
  'Início planejado': 'Inicio planificado',
  'Início — fim planejado': 'Inicio — fin planificado',
  'Linha base (início)': 'Línea base (inicio)',
  'Linha de base': 'Línea base',
  'Linha de base atual:': 'Línea base actual:',
  'Marco': 'Hito',
  'Marco:': 'Hito:',
  'Margem': 'Margen',
  'Movendo…': 'Moviendo…',
  'Mover': 'Mover',
  'Mover para baixo': 'Mover hacia abajo',
  'Mover para cima': 'Mover hacia arriba',
  'Mover tarefa': 'Mover tarea',
  'Mínimo de 8 caracteres.': 'Mínimo de 8 caracteres.',
  'Nenhum': 'Ninguno',
  'Nenhum calendário cadastrado ainda.': 'Ningún calendario registrado todavía.',
  'Nenhum cliente cadastrado ainda.': 'Ningún cliente registrado todavía.',
  'Nenhum feriado cadastrado para este calendário.': 'Ningún feriado registrado para este calendario.',
  'Nenhum projeto no seu escopo ainda.': 'Ningún proyecto en su alcance todavía.',
  'Nenhum recurso alocado — o Trabalho usa uma FTE genérica de 8h/dia.': 'Ningún recurso asignado — el Trabajo usa una FTE genérica de 8h/día.',
  'Nenhum usuário cadastrado ainda.': 'Ningún usuario registrado todavía.',
  'Nenhuma': 'Ninguna',
  'Nenhuma (raiz)': 'Ninguna (raíz)',
  'Nenhuma linha de base salva ainda para este projeto.': 'Ninguna línea base guardada todavía para este proyecto.',
  'Nenhuma tarefa cadastrada ainda.': 'Ninguna tarea registrada todavía.',
  'Nenhuma tarefa tem datas planejadas ainda — o Gantt aparece assim que houver início/fim planejados.': 'Ninguna tarea tiene fechas planificadas todavía — el Gantt aparece en cuanto haya inicio/fin planificados.',
  'Nenhuma — a data de início desta tarefa fica manual.': 'Ninguna — la fecha de inicio de esta tarea queda manual.',
  'Nome': 'Nombre',
  'Nome da tarefa': 'Nombre de la tarea',
  'Nome da versão': 'Nombre de la versión',
  'Nome do contato': 'Nombre del contacto',
  'Nome fantasia': 'Nombre comercial',
  'Nova predecessora': 'Nueva predecesora',
  'Nova senha': 'Nueva contraseña',
  'Nova tarefa pai': 'Nueva tarea padre',
  'Novo calendário': 'Nuevo calendario',
  'Novo cliente': 'Nuevo cliente',
  'Novo projeto': 'Nuevo proyecto',
  'Novo usuário': 'Nuevo usuario',
  'Não cadastrado': 'No registrado',
  'Obrigatório para perfis do cliente.': 'Obligatorio para perfiles del cliente.',
  'Observações': 'Observaciones',
  'Opcional.': 'Opcional.',
  'Pacote vendido (horas × valor/hora)': 'Paquete vendido (horas × valor/hora)',
  'Padrão (segunda a sexta, sem feriados)': 'Predeterminado (lunes a viernes, sin feriados)',
  'Perfil': 'Perfil',
  'Por último': 'Al final',
  'Portfólio de projetos no seu escopo.': 'Portafolio de proyectos en su alcance.',
  'Precisa ser ADMIN ou gerente de projetos interno.': 'Debe ser ADMIN o gerente de proyectos interno.',
  'Predecessora(s)': 'Predecesora(s)',
  'Predecessoras': 'Predecesoras',
  'Progresso': 'Progreso',
  'Progresso médio': 'Progreso promedio',
  'Projeto': 'Proyecto',
  'Próximo marco': 'Próximo hito',
  'Razão social': 'Razón social',
  'Real': 'Real',
  'Recalculando WBS/EAP…': 'Recalculando WBS/EAP…',
  'Recalculando datas do projeto…': 'Recalculando fechas del proyecto…',
  'Recalcular WBS/EAP': 'Recalcular WBS/EAP',
  'Recalcular tudo': 'Recalcular todo',
  'Recurso': 'Recurso',
  'Recurso (custo/h)': 'Recurso (costo/h)',
  'Recursos': 'Recursos',
  'Recursos alocados': 'Recursos asignados',
  'Redefinir senha': 'Restablecer contraseña',
  'Remover': 'Quitar',
  'Restaurar padrão': 'Restaurar predeterminado',
  'Restaurar período do projeto': 'Restaurar período del proyecto',
  'Salvar linha de base': 'Guardar línea base',
  'Selecione a tarefa predecessora.': 'Seleccione la tarea predecesora.',
  'Selecione o recurso e informe as horas alocadas.': 'Seleccione el recurso e indique las horas asignadas.',
  'Selecione um calendário na lista ao lado para ver e cadastrar feriados.': 'Seleccione un calendario en la lista al lado para ver y registrar feriados.',
  'Selecione…': 'Seleccione…',
  'Sem predecessora, esta data fica manual.': 'Sin predecesora, esta fecha queda manual.',
  'Senha provisória': 'Contraseña provisoria',
  'Seu perfil não tem acesso a dados financeiros deste projeto.': 'Su perfil no tiene acceso a los datos financieros de este proyecto.',
  'Situação': 'Situación',
  'Status': 'Estado',
  'Tarefa pai': 'Tarea padre',
  'Tarefas': 'Tareas',
  'Tarefas atrasadas': 'Tareas atrasadas',
  'Tarefas por status': 'Tareas por estado',
  'Tarefas por tipo': 'Tareas por tipo',
  'Tarefas restantes': 'Tareas restantes',
  'Telefone do contato': 'Teléfono del contacto',
  'Tem certeza que quer apagar': '¿Está seguro de que quiere eliminar',
  'Tem certeza que quer excluir o feriado': '¿Está seguro de que quiere eliminar el feriado',
  'Tipo': 'Tipo',
  'Trabalho': 'Trabajo',
  'Trabalho (horas)': 'Trabajo (horas)',
  'Trabalho na linha base:': 'Trabajo en la línea base:',
  'Término': 'Término',
  'Usado para calcular dias úteis nas datas planejadas.': 'Usado para calcular días hábiles en las fechas planificadas.',
  'Use "Recalcular WBS/EAP" para renumerar.': 'Use "Recalcular WBS/EAP" para renumerar.',
  'Usuários internos e externos, e o custo/capacidade de cada um como recurso alocável.': 'Usuarios internos y externos, y el costo/capacidad de cada uno como recurso asignable.',
  'Valor de faturamento (US$/h)': 'Valor de facturación (US$/h)',
  'Valor total vendido (calculado):': 'Valor total vendido (calculado):',
  'Valor vendido': 'Valor vendido',
  'Valor/h consultoria': 'Valor/h consultoría',
  'Valor/h gestão': 'Valor/h gestión',
  'Variância de término': 'Variación de término',
  'Vincular como recurso': 'Vincular como recurso',
  'Vincular recurso': 'Vincular recurso',
  'Visão geral do portfólio de projetos.': 'Visión general del portafolio de proyectos.',
  'alocadas': 'asignadas',
  'predecessora': 'predecesora',
  'predecessoras': 'predecesoras',
  'salva em': 'guardada en',
  'sem datas': 'sin fechas',
  'É um marco (milestone)': 'Es un hito (milestone)',
  'Excluir usuário': 'Eliminar usuario',
  'Tem certeza que quer excluir o usuário': '¿Está seguro de que quiere eliminar el usuario',
  'Excluir projeto': 'Eliminar proyecto',
  'Tem certeza que quer excluir o projeto': '¿Está seguro de que quiere eliminar el proyecto',
  'Só é possível excluir um projeto que ainda não tenha nenhuma tarefa cadastrada.': 'Solo es posible eliminar un proyecto que aún no tenga ninguna tarea registrada.',

  // --- Tela de Login (redesenho a partir da referência Resultar Servicios) ---
  Mostrar: 'Mostrar',
  Ocultar: 'Ocultar',
  'Preciso recuperar meu acesso': 'Necesito recuperar mi acceso',
  'A redefinição de senha deve ser solicitada ao Administrador.': 'El restablecimiento de contraseña debe solicitarse al Administrador.',
  'Acesso privado da organização': 'Acceso privado de la organización',
  'Os usuários e permissões são administrados pelo Administrador.': 'Los usuarios y permisos son administrados por el Administrador.',
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
