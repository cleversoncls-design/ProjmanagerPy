from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.database import reset_database_state


@pytest.fixture()
def rate_limited_app(monkeypatch):
    """Recarrega `app.main` com o rate limiting habilitado, isolado do
    restante da suíte.

    O resto dos testes roda com `RATE_LIMIT_MAX_REQUESTS` indefinida (padrão
    0 = desabilitado) justamente para nunca falhar por flakiness de limite
    de requisições; este teste liga a variável só para si e recarrega o
    módulo para que o middleware seja registrado com o novo valor.
    """
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    reset_database_state()

    import app.main as main_module

    importlib.reload(main_module)
    try:
        with TestClient(main_module.app) as test_client:
            yield test_client
    finally:
        reset_database_state()


def test_rate_limit_blocks_after_max_requests(rate_limited_app):
    first = rate_limited_app.get("/health")
    second = rate_limited_app.get("/health")
    third = rate_limited_app.get("/health")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_rate_limit_disabled_by_default(client):
    """Sem `RATE_LIMIT_MAX_REQUESTS` definida, nenhuma requisição é
    bloqueada — o middleware nem é registrado na aplicação."""
    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200
