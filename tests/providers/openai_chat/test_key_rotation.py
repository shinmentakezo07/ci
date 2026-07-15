"""Tests for OpenAI-chat provider API key rotation."""

from free_claude_code.providers.base import ProviderConfig
from free_claude_code.providers.openai_chat import OpenAIChatProfile, OpenAIChatProvider
from free_claude_code.providers.openai_chat.request_policy import (
    OpenAIChatRequestPolicy,
)
from free_claude_code.providers.rate_limit import ProviderRateLimiter

REQUEST_POLICY = OpenAIChatRequestPolicy(provider_name="TEST")


def test_openai_chat_provider_uses_extra_headers_for_key():
    config = ProviderConfig(
        api_keys=("key-a", "key-b"),
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
    assert provider._api_key_ring is not None
    assert len(provider._api_key_ring) == 2
    headers1 = provider._auth_headers()
    headers2 = provider._auth_headers()
    assert headers1 == {"Authorization": "Bearer key-a"}
    assert headers2 == {"Authorization": "Bearer key-b"}
