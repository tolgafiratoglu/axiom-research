"""Gemini client — same wire path as travel-rag (google-genai).

Model ID is ``settings.gemini_model`` at runtime. No Flash-Lite thinking
profile; Gemini 3.x must not send temperature/top_p/top_k.
"""

from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from axiom_research.settings import require_gemini, settings

_client: genai.Client | None = None
_MAX_OUTPUT_TOKENS = 4096


def _generation_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(max_output_tokens=_MAX_OUTPUT_TOKENS)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        ready = require_gemini(settings)
        _client = genai.Client(api_key=ready.gemini_api_key)
    return _client


def _extract_text(response) -> str:
    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates")
    text = response.text
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text


class GeminiProvider:
    async def generate(
        self,
        prompt: str,
        *,
        stream: bool = False,
        model: str | None = None,
    ) -> str:
        if stream:
            parts: list[str] = []
            async for delta in self.stream_generate(prompt, model=model):
                parts.append(delta)
            return "".join(parts)

        ready = require_gemini(settings)
        response = await _get_client().aio.models.generate_content(
            model=model or ready.gemini_model,
            contents=prompt,
            config=_generation_config(),
        )
        return _extract_text(response)

    async def stream_generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        ready = require_gemini(settings)
        async for chunk in await _get_client().aio.models.generate_content_stream(
            model=model or ready.gemini_model,
            contents=prompt,
            config=_generation_config(),
        ):
            text = getattr(chunk, "text", None)
            if text:
                yield text

    async def warmup(self) -> None:
        pass
