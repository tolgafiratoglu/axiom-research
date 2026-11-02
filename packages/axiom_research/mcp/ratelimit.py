import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from axiom_research.mcp.errors import McpRuntimeError

HEALTH_PATHS = frozenset({"/health", "/healthz"})


class RateLimiter:
    def __init__(self, *, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str, *, now: float | None = None) -> None:
        current = now if now is not None else time.monotonic()
        window_start = current - self.window_seconds
        hits = [stamp for stamp in self._hits.get(key, []) if stamp > window_start]
        if len(hits) >= self.max_requests:
            self._hits[key] = hits
            raise McpRuntimeError(
                "RATE_LIMIT",
                "request rate exceeded",
                retryable=True,
            )
        hits.append(current)
        self._hits[key] = hits


class RateLimitMiddleware:
    """In-process rate limit by client address. No auth."""

    def __init__(self, app: ASGIApp, *, limiter: RateLimiter):
        self.app = app
        self._limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in HEALTH_PATHS:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        key = client[0] if client else "unknown"
        try:
            self._limiter.check(key)
        except McpRuntimeError as exc:
            response = JSONResponse(exc.as_dict(), status_code=429)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
