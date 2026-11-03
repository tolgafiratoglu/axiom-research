"""In-memory session event log for WS replay via ``last_event_id``."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any

from api.telemetry import assert_no_private_cot, scrub_private_cot
from axiom_research.events import SERVER_ADAPTER, ServerMessage


class EventLog:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._events: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def append(self, event: ServerMessage | dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict):
            payload = event.model_dump(mode="json")
        else:
            payload = dict(event)
        payload = scrub_private_cot(payload)
        assert isinstance(payload, dict)
        assert_no_private_cot(payload)
        if "event_id" not in payload or not payload["event_id"]:
            payload["event_id"] = f"evt-{next(self._ids)}"
        if "ts" not in payload:
            payload["ts"] = datetime.now(tz=UTC)
        if "session_id" not in payload:
            payload["session_id"] = self.session_id
        # Validate stable UI contract (raises on unknown/raw SDK shapes).
        SERVER_ADAPTER.validate_python(payload)
        dumped = SERVER_ADAPTER.validate_python(payload).model_dump(mode="json")
        self._events.append(dumped)
        return dumped

    def events_after(self, last_event_id: str | None) -> list[dict[str, Any]]:
        if not last_event_id:
            return list(self._events)
        idx = next(
            (i for i, e in enumerate(self._events) if e["event_id"] == last_event_id),
            None,
        )
        if idx is None:
            return list(self._events)
        return list(self._events[idx + 1 :])

    @property
    def last_event_id(self) -> str | None:
        if not self._events:
            return None
        return str(self._events[-1]["event_id"])
