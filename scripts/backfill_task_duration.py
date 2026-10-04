"""Corrige `Task.duration_days` de tarefas antigas, criadas antes da coluna
existir (migração 0003, Fase 4).

A migração adicionou `duration_days` com `server_default="1"` — decisão
correta para não quebrar linhas já existentes na hora do ALTER TABLE, mas
que deixou toda tarefa criada antes disso com duration_days=1, mesmo
quando `planned_start_date`/`planned_end_date` já registravam um intervalo
real de vários dias. Isso não é só um problema cosmético na grade: Duração
é a fonte da verdade do motor de agendamento (ver `services.
_end_date_from_duration`/`apply_effort_driven`) — qualquer recálculo de
cascata ou de WBS numa tarefa dessas usaria os 1 dia errado e encolheria
silenciosamente uma tarefa que na real dura semanas.

Este script recalcula duration_days a partir do intervalo já registrado
em planned_start_date/planned_end_date (dias úteis pelo calendário do
projeto), mas só corrige o que tem cara de ter sido pego pelo default:

  - só tarefas SEM filhas (tarefa-pai não usa duration_days própria — ver
    services._task_rollups, que já agrega isso sob demanda a partir das
    folhas);
  - só onde duration_days == 1 hoje (o valor suspeito do default) E o
    intervalo de datas já registrado implica mais de 1 dia útil.

Nunca sobrescreve uma tarefa que já tenha uma duração > 1 dia gravada
(pode ter sido ajustada de propósito depois) nem uma sem datas planejadas
(não há intervalo pra recalcular a partir de nada).

Uso (dry-run primeiro, sempre):

    docker compose exec api python -m scripts.backfill_task_duration --dry-run
    docker compose exec api python -m scripts.backfill_task_duration
"""
from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models import Project, Task
from app.services import BusinessCalendar, _duration_days, calendar_for_project


def _leaf_task_ids(session: Session, project_id: str) -> set[str]:
    tasks = session.scalars(select(Task).where(Task.project_id == project_id)).all()
    parent_ids = {t.parent_task_id for t in tasks if t.parent_task_id}
    return {t.id for t in tasks if t.id not in parent_ids}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recalcula duration_days de tarefas-folha antigas a partir de planned_start_date/planned_end_date."
    )
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o que mudaria, sem gravar nada.")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        changed = 0
        for project in session.scalars(select(Project)).all():
            cal: BusinessCalendar = calendar_for_project(session, project)
            leaf_ids = _leaf_task_ids(session, project.id)
            tasks = session.scalars(
                select(Task).where(Task.project_id == project.id, Task.id.in_(leaf_ids))
            ).all()
            for task in tasks:
                if Decimal(task.duration_days) != Decimal("1"):
                    continue  # já foi editada/definida de propósito — não mexe.
                if not task.planned_start_date or not task.planned_end_date:
                    continue  # sem intervalo pra recalcular a partir de nada.
                real_duration = _duration_days(cal, task.planned_start_date, task.planned_end_date)
                if real_duration <= 1:
                    continue  # duration_days=1 já está correto pra esse intervalo.
                print(
                    f"[{project.code}] {task.wbs_code} {task.name!r}: "
                    f"duration_days 1 -> {real_duration} "
                    f"({task.planned_start_date} a {task.planned_end_date})"
                )
                changed += 1
                if not args.dry_run:
                    task.duration_days = Decimal(real_duration)
        if args.dry_run:
            print(f"\n{changed} tarefa(s) seriam corrigidas (--dry-run, nada foi gravado).")
        else:
            session.commit()
            print(f"\n{changed} tarefa(s) corrigidas.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
