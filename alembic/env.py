from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import build_database_url
from app.models import Base

# Objeto de configuração do Alembic, com acesso aos valores de alembic.ini.
config = context.config

# Sobrescreve a URL do .ini com a mesma lógica usada pela API (DATABASE_URL >
# POSTGRES_* > fallback SQLite), para nunca haver duas fontes de verdade
# divergentes sobre a conexão do banco.
config.set_main_option("sqlalchemy.url", build_database_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# metadata usada por `alembic revision --autogenerate` para comparar o
# schema declarado em app/models.py com o estado real do banco.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem abrir conexão com o banco
    (`alembic upgrade head --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrações com uma conexão real ao banco (modo padrão)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
