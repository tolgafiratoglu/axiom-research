from collections.abc import Awaitable, Callable
from typing import Any

import httpx2

from axiom_research.mcp.errors import McpRuntimeError, redact
from axiom_research.mcp.policy import assert_metadata_only

DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_RETRIES = 3
RETRY_AFTER_CAP_SECONDS = 10.0
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

SleepFn = Callable[[float], Awaitable[None]]


class UpstreamClient:
    """Timeout, retry, schema-untrusted JSON GET. No live calls in unit tests."""

    def __init__(
        self,
        http: httpx2.AsyncClient,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_after_cap: float = RETRY_AFTER_CAP_SECONDS,
        sleep: SleepFn | None = None,
        secrets: tuple[str, ...] = (),
    ):
        self._http = http
        self._max_retries = max_retries
        self._retry_after_cap = retry_after_cap
        self._sleep: SleepFn = sleep or _async_sleep
        self._secrets = secrets

    async def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = await self._request(url, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise McpRuntimeError(
                "VALIDATION",
                "upstream returned non-JSON payload",
            ) from exc

    async def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        response = await self._request(url, params=params)
        return response.text

    async def _request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx2.Response:
        assert_metadata_only(url=url)
        last_error: McpRuntimeError | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._http.get(url, params=params)
            except httpx2.TimeoutException:
                last_error = McpRuntimeError(
                    "UPSTREAM_TIMEOUT",
                    "upstream timeout",
                    retryable=True,
                )
                if attempt == self._max_retries:
                    raise last_error
                await self._sleep(min(2**attempt, self._retry_after_cap))
                continue
            except httpx2.HTTPError as exc:
                last_error = McpRuntimeError(
                    "UPSTREAM_ERROR",
                    redact(str(exc), self._secrets),
                    retryable=True,
                )
                if attempt == self._max_retries:
                    raise last_error
                await self._sleep(min(2**attempt, self._retry_after_cap))
                continue

            if response.status_code == 200:
                return response

            if response.status_code == 429:
                raw_retry = response.headers.get("Retry-After", "1")
                try:
                    retry_after = min(float(raw_retry), self._retry_after_cap)
                except ValueError:
                    retry_after = self._retry_after_cap
                last_error = McpRuntimeError(
                    "UPSTREAM_RATE_LIMIT",
                    "upstream rate limit",
                    retryable=True,
                )
                if attempt == self._max_retries:
                    raise last_error
                await self._sleep(retry_after)
                continue

            if response.status_code in RETRY_STATUS_CODES:
                last_error = McpRuntimeError(
                    "UPSTREAM_ERROR",
                    f"upstream returned {response.status_code}",
                    retryable=True,
                )
                if attempt == self._max_retries:
                    raise last_error
                await self._sleep(min(2**attempt, self._retry_after_cap))
                continue

            if response.status_code == 404:
                raise McpRuntimeError("NOT_FOUND", "upstream resource not found")

            raise McpRuntimeError(
                "UPSTREAM_ERROR",
                f"upstream returned {response.status_code}",
            )

        assert last_error is not None
        raise last_error


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
