"""Scripted Strands Model for Swarm unit tests (no live Gemini)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from strands.models import Model

ScriptFn = Callable[[list[Any], list[Any] | None], AsyncIterator[dict[str, Any]]]


class ScriptedModel(Model):
    """Replay a list of stream scripts; last script repeats if exhausted."""

    def __init__(self, scripts: list[ScriptFn]) -> None:
        self.scripts = list(scripts)
        self.i = 0

    def update_config(self, **kwargs: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {}

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("ScriptedModel does not support structured_output")

    async def stream(
        self,
        messages: list[Any],
        tool_specs: list[Any] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        idx = min(self.i, len(self.scripts) - 1)
        script = self.scripts[idx]
        self.i += 1
        async for event in script(messages, tool_specs):
            yield event


def text_turn(text: str = "complete", *, input_tokens: int = 10, output_tokens: int = 5) -> ScriptFn:
    async def script(messages: list[Any], tool_specs: list[Any] | None) -> AsyncIterator[dict[str, Any]]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
                "metrics": {"latencyMs": 1},
            }
        }

    return script


def tool_turn(
    name: str,
    arguments: dict[str, Any],
    *,
    tool_use_id: str = "tool-1",
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> ScriptFn:
    async def script(messages: list[Any], tool_specs: list[Any] | None) -> AsyncIterator[dict[str, Any]]:
        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockStart": {
                "start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}
            }
        }
        yield {
            "contentBlockDelta": {
                "delta": {"toolUse": {"input": json.dumps(arguments)}}
            }
        }
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
                "metrics": {"latencyMs": 1},
            }
        }

    return script


def handoff_turn(agent_name: str, message: str, **kwargs: Any) -> ScriptFn:
    return tool_turn(
        "handoff_to_agent",
        {"agent_name": agent_name, "message": message},
        tool_use_id=f"handoff-{agent_name}",
        **kwargs,
    )
