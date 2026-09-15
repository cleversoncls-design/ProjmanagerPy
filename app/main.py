from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .database import init_db
from .routers import (
    auth,
    baselines,
    calendars,
    changes,
    clients,
    expenses,
    intakes,
    projects,
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
