DO $$
BEGIN
  CREATE TYPE taskpriority AS ENUM ('LOW', 'MED', 'HIGH');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  CREATE TYPE tasktype AS ENUM ('IMPLEMENTATION', 'DEVELOPMENT', 'USER_VALIDATION', 'MEETING');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS duration_days INTEGER NOT NULL DEFAULT 1;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority taskpriority NOT NULL DEFAULT 'MED';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS task_type tasktype NOT NULL DEFAULT 'IMPLEMENTATION';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS observation TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS baseline_id VARCHAR(36);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_tasks_baseline_id'
  ) THEN
    ALTER TABLE tasks
      ADD CONSTRAINT fk_tasks_baseline_id
      FOREIGN KEY (baseline_id) REFERENCES baselines(id) ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_tasks_baseline_id ON tasks (baseline_id);
UPDATE tasks SET duration_days = 1 WHERE duration_days IS NULL OR duration_days < 1;
