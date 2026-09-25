"""Tradução das mensagens de erro da API (pt-BR/es).

Segue o mesmo estilo "gettext" do frontend (ver frontend/src/i18n/
translations.js): a mensagem em PORTUGUÊS já escrita em cada
`HTTPException(detail=...)` continua sendo a própria chave de tradução —
não precisa inventar/manter um catálogo de slugs em paralelo ao texto real.
`t("Projeto não encontrado", user.language)` devolve a mensagem em
Espanhol quando `user.language == Language.ES`; em Português (padrão) ou
para qualquer texto que não esteja no dicionário, devolve o texto
original sem quebrar — uma mensagem nova que algum router venha a
adicionar simplesmente aparece em Português até alguém preencher a
tradução aqui.
"""
from __future__ import annotations

from .models import Language

# Só a tradução ES->PT-BR original faz sentido guardar — pt-BR é o próprio
# texto que já está espalhado pelos routers.
_ES: dict[str, str] = {
    "Alocação não encontrada": "Asignación no encontrada",
    "Apontamento não encontrado": "Registro de horas no encontrado",
    "Calendário não encontrado": "Calendario no encontrado",
    "Cliente não encontrado": "Cliente no encontrado",
    "Cliente precisa informar project_id": "El cliente debe informar project_id",
    "Conflito de integridade de dados (registro duplicado ou referência inválida).": (
        "Conflicto de integridad de datos (registro duplicado o referencia inválida)."
    ),
    "Credenciais inválidas": "Credenciales inválidas",
    "Dependência não encontrada": "Dependencia no encontrada",
    "Essa dependência já existe": "Esa dependencia ya existe",
    "Este usuário já possui um recurso cadastrado": "Este usuario ya tiene un recurso registrado",
    "Feriado não encontrado": "Feriado no encontrado",
    "Fora do escopo do cliente": "Fuera del alcance del cliente",
    "Informe project_id ou task_id": "Informe project_id o task_id",
    "Já existe um apontamento deste recurso nesta tarefa para esta data": "Ya existe un registro de horas de este recurso en esta tarea para esta fecha",
    "Já existe um cliente com este código": "Ya existe un cliente con este código",
    "Já existe um feriado cadastrado nesta data para este calendário": "Ya existe un feriado registrado en esta fecha para este calendario",
    "Já existe um projeto com este código": "Ya existe un proyecto con este código",
    "Já existe um usuário com este e-mail": "Ya existe un usuario con este correo electrónico",
    "Já existe uma tarefa com este código WBS neste projeto": "Ya existe una tarea con este código WBS en este proyecto",
    "Não é possível apagar uma tarefa que já tem apontamento de horas registrado.": (
        "No es posible eliminar una tarea que ya tiene horas registradas."
    ),
    "Não é possível apagar uma tarefa que tem tarefas-filhas. Mova ou apague as filhas primeiro.": (
        "No es posible eliminar una tarea que tiene tareas hijas. Mueva o elimine las hijas primero."
    ),
    "Perfil sem permissão de escrita": "Perfil sin permiso de escritura",
    "Perfil sem permissão para esta operação": "Perfil sin permiso para esta operación",
    "Perfis de cliente exigem client_id": "Los perfiles de cliente requieren client_id",
    "Predecessora e sucessora precisam pertencer ao mesmo projeto": "La predecesora y la sucesora deben pertenecer al mismo proyecto",
    "Projeto fora do escopo do cliente": "Proyecto fuera del alcance del cliente",
    "Projeto não encontrado": "Proyecto no encontrado",
    "Recurso já alocado nesta tarefa": "Recurso ya asignado a esta tarea",
    "Recurso não encontrado": "Recurso no encontrado",
    "Recurso não está alocado nesta tarefa": "El recurso no está asignado a esta tarea",
    "Recurso está alocado em uma ou mais tarefas — remova as alocações antes de excluir": "El recurso está asignado a una o más tareas — quite las asignaciones antes de eliminarlo",
    "Recurso tem apontamento de horas em projetos/tarefas — não pode ser excluído": "El recurso tiene horas registradas en proyectos/tareas — no se puede eliminar",
    "O recurso do Administrador não pode ser excluído": "El recurso del Administrador no se puede eliminar",
    "Risco não encontrado": "Riesgo no encontrado",
    "Solicitação de mudança não encontrada": "Solicitud de cambio no encontrada",
    "Solicitação não encontrada": "Solicitud no encontrada",
    "Somente o PM do cliente pode solicitar um novo projeto": "Solo el PM del cliente puede solicitar un nuevo proyecto",
    "Só o cliente valida suas próprias tarefas": "Solo el cliente valida sus propias tareas",
    "Só é possível apontar horas em projetos ativos": "Solo se pueden registrar horas en proyectos activos",
    "Tarefa já está aguardando validação do cliente": "La tarea ya está esperando la validación del cliente",
    "Tarefa não encontrada": "Tarea no encontrada",
    "Tarefa não está aguardando validação do cliente": "La tarea no está esperando la validación del cliente",
    "Token de acesso ausente": "Token de acceso ausente",
    "Token inválido ou expirado": "Token inválido o expirado",
    "Uma tarefa não pode depender de si mesma": "Una tarea no puede depender de sí misma",
    "Usuário inativo ou bloqueado": "Usuario inactivo o bloqueado",
    "Usuário inválido ou inativo": "Usuario inválido o inactivo",
    "Usuário não encontrado": "Usuario no encontrado",
    "Usuário não possui recurso habilitado": "El usuario no tiene un recurso habilitado",
    "manager_id precisa ser um usuário interno (ADMIN ou INTERNAL_PM)": "manager_id debe ser un usuario interno (ADMIN o INTERNAL_PM)",
    "parent_task_id precisa ser uma tarefa do mesmo projeto": "parent_task_id debe ser una tarea del mismo proyecto",
    "start precisa ser anterior ou igual a end": "start debe ser anterior o igual a end",
    "status precisa ser APPROVED ou REJECTED": "status debe ser APPROVED o REJECTED",
}


def t(text: str, lang: str | Language | None) -> str:
    """Traduz uma mensagem de erro. `lang` normalmente é `user.language`
    (string ou o enum `Language`); aceita `None` (endpoint sem usuário
    resolvido ainda) e cai no texto original em Português."""
    if lang == Language.ES or lang == "es":
        return _ES.get(text, text)
    return text


def request_language(request) -> str:
    """Fallback de idioma pra mensagens de erro emitidas ANTES de
    resolver um usuário (token ausente/inválido, ou e-mail que não bate
    com nenhum usuário no login) — nesses casos não existe `user.language`
    pra consultar. O frontend manda o idioma escolhido (ou o salvo no
    navegador antes mesmo de logar) no header `X-App-Language`; sem o
    header, cai em Português."""
    lang = request.headers.get("x-app-language")
    return lang if lang == "es" else Language.PT_BR
