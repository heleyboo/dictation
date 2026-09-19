from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import LlmUsage
from app.services.llm_client import AnthropicLlm, LlmError


class Answer(BaseModel):
    text: str


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class Response:
    stop_reason: str
    parsed_output: Answer | None
    usage: Usage


class FakeMessages:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Response:
        self.kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, response: Response) -> None:
        self.messages = FakeMessages(response)


def _llm(sessions: async_sessionmaker[AsyncSession], response: Response) -> tuple[AnthropicLlm, FakeClient]:
    client = FakeClient(response)
    return AnthropicLlm("claude-haiku-4-5", client=client, usage_sessions=lambda: sessions), client  # type: ignore[arg-type]


async def _usage(sessions: async_sessionmaker[AsyncSession]) -> list[tuple[str, str, int, int]]:
    async with sessions() as db:
        rows = await db.execute(
            select(LlmUsage.purpose, LlmUsage.model, LlmUsage.input_tokens, LlmUsage.output_tokens)
        )
        return [tuple(r) for r in rows]


async def test_parse_returns_structured_output_and_logs_usage(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    llm, client = _llm(sessions, Response("end_turn", Answer(text="xin chào"), Usage(120, 30)))
    answer = await llm.parse(purpose="translate", system="sys", prompt="hi", schema=Answer)
    assert answer == Answer(text="xin chào")
    assert client.messages.kwargs["model"] == "claude-haiku-4-5"
    assert client.messages.kwargs["output_format"] is Answer
    assert await _usage(sessions) == [("translate", "claude-haiku-4-5", 120, 30)]


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
async def test_unusable_answer_raises_but_spend_is_still_recorded(
    sessions: async_sessionmaker[AsyncSession], stop_reason: str
) -> None:
    llm, _ = _llm(sessions, Response(stop_reason, None, Usage(500, 16000)))
    with pytest.raises(LlmError):
        await llm.parse(purpose="translate", system="sys", prompt="hi", schema=Answer)
    assert await _usage(sessions) == [("translate", "claude-haiku-4-5", 500, 16000)]
