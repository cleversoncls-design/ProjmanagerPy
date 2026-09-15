from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting básico por cliente, com janela deslizante em memória.

    Desativado por padrão (`RATE_LIMIT_MAX_REQUESTS=0`, o valor default) para
    não introduzir flakiness na suíte de testes nem exigir infraestrutura
    externa (Redis, etc.) para uma primeira barreira simples contra abuso.
    O estado vive na memória do processo, então cada worker/réplica tem seu
    próprio contador — não é uma solução distribuída, mas já limita um
    cliente único martelando a API de uma instância.

    A chave de identificação do cliente prioriza o header `Authorization`
    (para não punir todos os usuários atrás do mesmo NAT/proxy por igual) e
    cai para `X-Forwarded-For`/IP da conexão quando a requisição não está
    autenticada (ex.: tentativas de login).
    """

    def __init__(self, app, max_requests: int, window_seconds: float):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        auth = request.headers.get("authorization")
        if auth:
            return auth
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if self.max_requests <= 0:
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - self.window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()

        if len(hits) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Muitas requisições. Tente novamente em instantes."},
            )

        hits.append(now)
        return await call_next(request)


def rate_limit_settings() -> tuple[int, float]:
    """Lê a configuração de rate limiting das variáveis de ambiente.

    `RATE_LIMIT_MAX_REQUESTS=0` (padrão) desativa o middleware inteiramente
    — nem chega a ser registrado na aplicação, para custo zero quando não
    está em uso.
    """
    max_requests = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "0"))
    window_seconds = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    return max_requests, window_seconds
