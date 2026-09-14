DO $$
BEGIN
  CREATE TYPE projectcurrency AS ENUM ('USD', 'PYG');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS currency projectcurrency NOT NULL DEFAULT 'USD';

ALTER TABLE projects
  ALTER COLUMN currency SET DEFAULT 'USD';

UPDATE projects
SET currency = 'USD'
WHERE currency IS NULL;

ALTER TABLE projects
  DROP CONSTRAINT IF EXISTS ck_projects_currency;

ALTER TABLE projects
  ADD CONSTRAINT ck_projects_currency CHECK (currency IN ('USD', 'PYG'));
