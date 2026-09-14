-- Migração idempotente do módulo de calendários por recurso.
-- O modelo SQLAlchemy cria estas estruturas em bancos novos; este arquivo
-- cobre bancos existentes sem apagar dados.

ALTER TABLE resources
  ADD COLUMN IF NOT EXISTS calendar_id VARCHAR(36);

CREATE INDEX IF NOT EXISTS ix_resources_calendar_id
  ON resources (calendar_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_resources_calendar_id_calendars'
  ) THEN
    ALTER TABLE resources
      ADD CONSTRAINT fk_resources_calendar_id_calendars
      FOREIGN KEY (calendar_id)
      REFERENCES calendars (id)
      ON DELETE SET NULL;
  END IF;
END $$;

-- Índice/unicidade para feriados já faz parte do modelo novo. A criação
-- condicional permite atualizar uma instalação que ainda não o possua.
CREATE UNIQUE INDEX IF NOT EXISTS uq_calendar_holiday
  ON holidays (calendar_id, date);

UPDATE resources
SET calendar_id = NULL
WHERE calendar_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM calendars WHERE calendars.id = resources.calendar_id);
