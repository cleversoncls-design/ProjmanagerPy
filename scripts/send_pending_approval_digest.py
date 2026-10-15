"""Manda, por e-mail, um resumo dos apontamentos aguardando aprovação para
cada gerente de projeto (pedido do usuário, caso 2 do "processo de envio
de emails": "Aviso de Registro de Horas/Tarefas para aprovar. (para o
gerente do projeto)" — decisão confirmada: "Resumo periódico", um e-mail
agrupando tudo que está pendente, em vez de um e-mail por apontamento).

Este ambiente de desenvolvimento não tem como agendar um job recorrente
de verdade (sem scheduler em processo, de propósito — ver docstring de
app/notifications.py) — quem agenda a RECORRÊNCIA é o usuário, no
servidor dele, com um cron do próprio sistema operacional apontando pra
este script. Ex. (todo dia às 8h):

    0 8 * * * cd /caminho/do/projeto && docker compose exec -T api python -m scripts.send_pending_approval_digest

Uso (dry-run primeiro, sempre, pra conferir quem receberia o quê sem
mandar nenhum e-mail de verdade):

    docker compose exec api python -m scripts.send_pending_approval_digest --dry-run
    docker compose exec api python -m scripts.send_pending_approval_digest
"""
from __future__ import annotations

import argparse

from app.database import get_session_factory
from app.notifications import send_pending_approval_digests


def main() -> int:
    parser = argparse.ArgumentParser(description="Manda o resumo de apontamentos pendentes de aprovação para cada gerente de projeto.")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra quem receberia o quê, sem mandar nenhum e-mail de verdade.")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        summaries = send_pending_approval_digests(session, dry_run=args.dry_run)
        if not args.dry_run:
            session.commit()
        if not summaries:
            print("Nenhum apontamento pendente de aprovação — nenhum e-mail a enviar.")
            return 0
        for summary in summaries:
            print(
                f"{summary['manager_name']} <{summary['manager_email']}>: "
                f"{summary['count']} apontamento(s), {summary['total_hours']}h"
                + (" (--dry-run, nada foi enviado)" if args.dry_run else "")
            )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
