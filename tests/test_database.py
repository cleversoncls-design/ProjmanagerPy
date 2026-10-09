from __future__ import annotations

from sqlalchemy.engine import make_url

from app.database import build_database_url


def test_build_database_url_prefers_explicit_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit.db")
    monkeypatch.setenv("POSTGRES_PASSWORD", "deve-ser-ignorada")

    assert build_database_url() == "sqlite:///explicit.db"


def test_build_database_url_keeps_the_real_password(monkeypatch):
    """Regressão: str(URL.create(...)) mascara a senha como "***" (padrão do
    SQLAlchemy desde a 1.4, para não vazar credenciais em logs) — usar isso
    como a URL de conexão de verdade faz a API sempre falhar com "password
    authentication failed", mesmo com a senha certa no .env. A senha real
    tem que aparecer na URL montada, não "***".
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "projmanager")
    monkeypatch.setenv("POSTGRES_PASSWORD", "@projmanager2026")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "projmanager")

    url = build_database_url()

    assert "***" not in url
    # Faz o mesmo parse que create_engine() faria: a senha real precisa
    # sobreviver ao round-trip (URL.create -> string -> make_url), não só
    # "não conter ***" — isso pegaria também um mascaramento parcial.
    assert make_url(url).password == "@projmanager2026"


def test_build_database_url_falls_back_to_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    assert build_database_url().startswith("sqlite:///")
