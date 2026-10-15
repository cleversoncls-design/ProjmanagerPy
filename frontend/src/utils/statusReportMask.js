/** Versão "segura pro cliente" de um Status Report já carregado na tela —
 * pedido do usuário: "não vejo opção de imprimir a versão para envio ao
 * cliente". Até aqui, o botão "Imprimir" só reproduzia exatamente o que o
 * backend já manda pro papel de quem está logado (ver `_serialize` em
 * app/routers/status_reports.py) — o que funciona pra um PM do cliente
 * logado no sistema, mas não dava ao gerente INTERNO (que é quem prepara
 * o relatório) nenhuma forma de gerar/imprimir a versão sem dado
 * financeiro pra mandar por fora (e-mail, PDF anexado etc.), sem precisar
 * logar como o cliente.
 *
 * Em vez de uma segunda chamada à API (o gerente já tem o relatório
 * completo em mãos), essa função aplica NO FRONTEND a mesma máscara que o
 * backend aplica pra EXTERNAL_ROLES — mesma lista de campos, mesmos
 * valores "nulos" (nunca um zero fajuto). Se a lista de campos ocultados
 * em `_serialize` mudar, essa função precisa mudar junto (comentário
 * espelhado nos dois lugares). */
export function maskStatusReportForClient(report) {
  return {
    ...report,
    next_steps_internal: null,
    hours_consumed: null,
    hours_budgeted: null,
    cost_planned: null,
    cost_actual: null,
    margin_planned_pct: null,
    margin_actual_pct: null,
    burndown: [],
  }
}
