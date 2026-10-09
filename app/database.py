from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def build_database_url() -> str:
    """Monta a URL de conexão a partir das variáveis de ambiente.

    Prioridade: DATABASE_URL explícita > variáveis POSTGRES_* > fallback
    SQLite local (usado em desenvolvimento sem Docker).
    """
    raw_database_url = os.getenv("DATABASE_URL")
    if raw_database_url:
        return raw_database_url
    if os.getenv("POSTGRES_PASSWORD"):
        # URL.create escapa a senha corretamente; '@', ':', '/', '#' etc. não quebram o hostname.
        #
        # IMPORTANTE: str(url) (ou repr(url)) mascara a senha como "***" —
        # é o comportamento padrão do SQLAlchemy desde a 1.4, pensado para
        # não vazar credenciais em logs. Usar str() aqui faria a aplicação
        # tentar autenticar literalmente com a senha "***", o que sempre
        # falharia com "password authentication failed" mesmo com a senha
        # certa no .env. render_as_string(hide_password=False) devolve a
        # senha de verdade.
        return URL.create(
            "postgresql+psycopg",
            username=os.getenv("POSTGRES_USER", "projmanager"),
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.getenv("POSTGRES_HOST", "db"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "projmanager"),
        ).render_as_string(hide_password=False)
    return "sqlite:///./controle_projetos.db"


# A engine é criada de forma preguiçosa (lazy) em vez de no import do módulo,
# para que os testes possam definir DATABASE_URL/POSTGRES_* antes de a
# primeira conexão acontecer, sem precisar de um banco real só para importar
# o pacote `app`.
_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        database_url = build_database_url()
        engine_kwargs: dict = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in database_url:
                # Sem isso, cada conexão do pool veria um banco :memory: vazio
                # e diferente — útil sobretudo nos testes de integração.
                engine_kwargs["poolclass"] = StaticPool
        _engine = create_engine(database_url, **engine_kwargs)
    return _engine


def get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def init_db() -> None:
    """Cria as tabelas que ainda não existem. Chamado no startup da API.

    Para produção, o próprio README já recomenda substituir por Alembic;
    isso continua adequado apenas para o primeiro ambiente/desenvolvimento.
    """
    Base.metadata.create_all(get_engine())


def reset_database_state() -> None:
    """Descarta a engine/sessionmaker em cache.

    Usado pelos testes de integração para trocar de banco (ex.: SQLite em
    memória isolado por teste) sem depender de variáveis de ambiente globais
    ou de reiniciar o processo.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db() -> Session:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
