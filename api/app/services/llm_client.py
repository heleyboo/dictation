"""The only module that calls the LLM. Every call is logged to `llm_usage` (NFR-11/12)."""

import logging
import time
from collections.abc import Callable
from typing import Protocol

import anthropic
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import session_factory
from app.models import LlmUsage

log = logging.getLogger("llm")


class LlmError(Exception):
    """The model did not return a usable structured answer (refusal, truncation, schema mismatch)."""


class StructuredLlm(Protocol):
    async def parse[T: BaseModel](self, *, purpose: str, system: str, prompt: str, schema: type[T]) -> T: ...


class AnthropicLlm:
    def __init__(
        self,
        model: str,
        client: anthropic.AsyncAnthropic | None = None,
        usage_sessions: Callable[[], async_sessionmaker[AsyncSession]] = session_factory,
    ) -> None:
        self._model = model
        self._client = client or anthropic.AsyncAnthropic()
        self._usage_sessions = usage_sessions

    async def _record(self, purpose: str, input_tokens: int, output_tokens: int, started: float) -> None:
        # Own transaction: spend on a call whose caller later fails/rolls back must still be counted.
        async with self._usage_sessions()() as db:
            db.add(
                LlmUsage(
                    purpose=purpose,
                    model=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=round((time.monotonic() - started) * 1000),
                    cache_hit=False,
                )
            )
            await db.commit()

    async def parse[T: BaseModel](self, *, purpose: str, system: str, prompt: str, schema: type[T]) -> T:
        started = time.monotonic()
        response = await self._client.messages.parse(
            model=self._model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        await self._record(purpose, response.usage.input_tokens, response.usage.output_tokens, started)
        if response.stop_reason != "end_turn" or response.parsed_output is None:
            log.warning("llm %s unusable: stop_reason=%s", purpose, response.stop_reason)
            raise LlmError(f"LLM returned no usable output (stop_reason={response.stop_reason})")
        return response.parsed_output
