from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .database import init_db
from .rate_limit import RateLimitMiddleware, rate_limit_settings
from .routers import (
    audit,
    auth,
    baselines,
    calendars,
    changes,
    clients,
    expenses,
    intakes,
    projects,
    reports,
    resources,
    risks,
    tasks,
    timesheets,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A criação da engine/sessionmaker é preguiçosa (ver app/database.py), e
    # `init_db()` só roda quando a aplicação de fato sobe — importar `app.main`
    # (como os testes fazem) não abre mais uma conexão de banco por si só.
    init_db()
    yield


app = FastAPI(title="Controle de Projetos Corporativo", version="0.2.0", lifespan=lifespan)


def _cors_origins() -> list[str]:
    """`CORS_ORIGINS` é uma lista separada por vírgulas de origens autorizadas
    (ex.: "https://app.exemplo.com,https://admin.exemplo.com"). Sem a
    variável definida, nenhuma origem de navegador é liberada — a API
    continua acessível normalmente via curl/Swagger/servidor-a-servidor,
    apenas sem os cabeçalhos de CORS que um browser exige."""
    raw = os.getenv("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sem isso, o Content-Disposition (nome do arquivo) da exportação de
    # tarefas (.xlsx) fica invisível pro JS do frontend em requisição
    # cross-origin (frontend e API em portas/hosts diferentes, caso comum
    # deste deploy) — o navegador só expõe os "response headers simples"
    # por padrão; o download em si não é afetado, só o nome do arquivo cai
    # pro fallback genérico (ver reports.js downloadTasksXlsx).
    expose_headers=["Content-Disposition"],
)

# Desligado por padrão (RATE_LIMIT_MAX_REQUESTS=0) — só entra na pilha de
# middlewares quando explicitamente habilitado, para não custar nada (nem
# risco de flakiness nos testes) quando não está em uso.
_rate_limit_max_requests, _rate_limit_window_seconds = rate_limit_settings()
if _rate_limit_max_requests > 0:
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=_rate_limit_max_requests,
        window_seconds=_rate_limit_window_seconds,
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Converte violações de integridade do banco (unicidade, FK, etc.) em uma
    resposta 409 previsível, em vez do 500 genérico que o SQLAlchemy/psycopg
    levantava antes."""
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "Conflito de integridade de dados (registro duplicado ou referência inválida)."})


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(intakes.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(resources.router)
app.include_router(timesheets.router)
app.include_router(expenses.router)
app.include_router(calendars.router)
app.include_router(risks.router)
app.include_router(changes.router)
app.include_router(baselines.router)
app.include_router(audit.router)
app.include_router(reports.router)
