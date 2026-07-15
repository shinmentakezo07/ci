"""Tests for OpenAI-chat provider key retry on auth/rate-limit failures."""

from typing import Any

import httpx
import openai
import pytest

from free_claude_code.providers.base import ProviderConfig
from free_claude_code.providers.openai_chat import OpenAIChatProfile, OpenAIChatProvider
from free_claude_code.providers.openai_chat.request_policy import (
    OpenAIChatRequestPolicy,
)
from free_claude_code.providers.rate_limit import ProviderRateLimiter

REQUEST_POLICY = OpenAIChatRequestPolicy(provider_name="TEST")


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _Chunk:
    def __init__(self):
        self.choices = [
            type(
                "C",
                (),
                {
                    "finish_reason": "stop",
                    "delta": type("D", (), {"content": "ok"})(),
                },
            )()
        ]


@pytest.mark.asyncio
async def test_openai_chat_retries_on_auth_error_with_next_key():
    config = ProviderConfig(
        api_keys=("bad-key", "good-key"),
        base_url="https://example.com/v1",
    )
    profile = OpenAIChatProfile(REQUEST_POLICY)
    provider = OpenAIChatProvider(
        config,
        profile=profile,
        rate_limiter=ProviderRateLimiter(
            rate_limit=10, rate_window=1, max_concurrency=1
        ),
    )

    calls = []

    async def fake_create(
        *, extra_headers: dict[str, str], stream: bool, **kwargs: Any
    ) -> _FakeStream:
        calls.append(extra_headers)
        if extra_headers["Authorization"] == "Bearer bad-key":
            response = httpx.Response(
                status_code=401,
                headers={},
                request=httpx.Request(
                    "POST", "https://example.com/v1/chat/completions"
                ),
            )
            raise openai.AuthenticationError(
                "Invalid key", response=response, body=None
            )
        return _FakeStream([_Chunk()])

    provider._client.chat.completions.create = fake_create  # type: ignore

    body = {"model": "test-model", "messages": []}
    stream, _ = await provider._create_stream(body)
    chunks = [chunk async for chunk in stream]
    assert len(calls) == 2
    assert calls[0]["Authorization"] == "Bearer bad-key"
    assert calls[1]["Authorization"] == "Bearer good-key"
    assert chunks
